#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import traceback

# 尝试导入所需的库
try:
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version, parse
    from tabulate import tabulate
    import colorama
    from colorama import Fore, Style
except ImportError as e:
    print(f"错误: 缺少必要的依赖库: {e}")
    print("请确保已安装以下依赖:")
    print("  - packaging")
    print("  - tabulate")
    print("  - colorama")
    print("\n可以使用以下命令安装:")
    print("  pip install packaging tabulate colorama")
    input("\n按回车键退出...")
    sys.exit(1)

# 初始化colorama
colorama.init()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('dependency_resolver')

@dataclass
class DependencyRequirement:
    """依赖需求类，用于存储依赖的名称和版本要求"""
    name: str
    specifier: SpecifierSet
    original_line: str
    plugin_name: str

    def __str__(self) -> str:
        return f"{self.name}{self.specifier}"

@dataclass
class ConflictInfo:
    """冲突信息类，用于存储冲突的依赖信息"""
    dependency_name: str
    conflicting_plugins: List[Tuple[str, str]]  # 插件名称和版本要求

class DependencyResolver:
    """依赖冲突解决工具的主类"""
    
    def __init__(self, plugins_dir: str):
        """
        初始化依赖解析器
        
        Args:
            plugins_dir: 插件目录的路径
        """
        self.plugins_dir = Path(plugins_dir)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = Path(script_dir) / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 存储所有插件的依赖需求
        self.all_requirements: Dict[str, List[DependencyRequirement]] = {}
        
        # 按依赖名称组织的需求
        self.dependency_requirements: Dict[str, List[DependencyRequirement]] = {}
        
    def scan_plugins(self) -> None:
        """扫描插件目录，解析所有requirements.txt文件"""
        logger.info(f"扫描插件目录: {self.plugins_dir}")
        
        if not self.plugins_dir.exists():
            logger.error(f"插件目录不存在: {self.plugins_dir}")
            print(f"{Fore.RED}错误: 插件目录不存在: {self.plugins_dir}{Style.RESET_ALL}")
            return
        
        # 遍历插件目录
        plugin_count = 0
        req_file_count = 0
        
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            plugin_count += 1
            plugin_name = plugin_dir.name
            req_file = plugin_dir / "requirements.txt"
            
            if not req_file.exists():
                logger.info(f"插件 {plugin_name} 没有requirements.txt文件，跳过")
                continue
            
            req_file_count += 1
            logger.info(f"解析插件 {plugin_name} 的requirements.txt文件")
            self.parse_requirements(plugin_name, req_file)
        
        if plugin_count == 0:
            print(f"{Fore.YELLOW}警告: 未在指定目录中找到任何插件文件夹{Style.RESET_ALL}")
        elif req_file_count == 0:
            print(f"{Fore.YELLOW}警告: 找到 {plugin_count} 个插件文件夹，但没有找到任何requirements.txt文件{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}成功扫描 {plugin_count} 个插件文件夹，找到 {req_file_count} 个requirements.txt文件{Style.RESET_ALL}")
    
    def parse_requirements(self, plugin_name: str, req_file: Path) -> None:
        """
        解析requirements.txt文件
        
        Args:
            plugin_name: 插件名称
            req_file: requirements.txt文件路径
        """
        requirements = []
        
        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue
                    
                    try:
                        # 使用packaging库解析依赖
                        req = Requirement(line)
                        dep_req = DependencyRequirement(
                            name=req.name.lower(),  # 统一使用小写名称
                            specifier=req.specifier,
                            original_line=line,
                            plugin_name=plugin_name
                        )
                        requirements.append(dep_req)
                        
                        # 按依赖名称组织
                        if dep_req.name not in self.dependency_requirements:
                            self.dependency_requirements[dep_req.name] = []
                        self.dependency_requirements[dep_req.name].append(dep_req)
                        
                    except Exception as e:
                        logger.warning(f"无法解析 {plugin_name} 的依赖 (行 {line_num}): {line}")
                        logger.warning(f"错误: {str(e)}")
        except Exception as e:
            logger.error(f"无法读取文件 {req_file}: {str(e)}")
            print(f"{Fore.RED}错误: 无法读取文件 {req_file}: {str(e)}{Style.RESET_ALL}")
            return
        
        self.all_requirements[plugin_name] = requirements
        logger.info(f"插件 {plugin_name} 解析完成，找到 {len(requirements)} 个依赖")
    
    def detect_conflicts(self) -> List[ConflictInfo]:
        """
        检测依赖冲突
        
        Returns:
            冲突信息列表
        """
        conflicts = []
        
        for dep_name, requirements in self.dependency_requirements.items():
            if len(requirements) <= 1:
                continue  # 只有一个插件使用此依赖，不可能冲突
            
            # 找出所有最低版本要求
            min_versions = {}
            for req in requirements:
                for spec in req.specifier:
                    if spec.operator in ('>=', '==', '>'):
                        if req.plugin_name not in min_versions:
                            min_versions[req.plugin_name] = (spec.version, spec.operator)
                        else:
                            current_ver, current_op = min_versions[req.plugin_name]
                            if parse(spec.version) > parse(current_ver):
                                min_versions[req.plugin_name] = (spec.version, spec.operator)
            
            # 找出所有最高版本要求
            max_versions = {}
            for req in requirements:
                for spec in req.specifier:
                    if spec.operator in ('<=', '==', '<'):
                        if req.plugin_name not in max_versions:
                            max_versions[req.plugin_name] = (spec.version, spec.operator)
                        else:
                            current_ver, current_op = max_versions[req.plugin_name]
                            if parse(spec.version) < parse(current_ver):
                                max_versions[req.plugin_name] = (spec.version, spec.operator)
            
            # 检查冲突：某些插件要求的最低版本高于其他插件要求的最高版本
            conflict_found = False
            conflicting_plugins = []
            
            for plugin_min, (min_ver, min_op) in min_versions.items():
                min_version = parse(min_ver)
                
                for plugin_max, (max_ver, max_op) in max_versions.items():
                    max_version = parse(max_ver)
                    
                    # 检查是否冲突
                    if min_version > max_version or (min_version == max_version and (min_op == '>' or max_op == '<')):
                        conflict_found = True
                        min_req_str = f"{min_op}{min_ver}" if min_op else ""
                        max_req_str = f"{max_op}{max_ver}" if max_op else ""
                        
                        # 获取完整的版本要求字符串
                        for req in requirements:
                            if req.plugin_name == plugin_min:
                                min_req_str = str(req.specifier)
                            if req.plugin_name == plugin_max:
                                max_req_str = str(req.specifier)
                        
                        conflicting_plugins.append((plugin_min, min_req_str))
                        if (plugin_max, max_req_str) not in conflicting_plugins:
                            conflicting_plugins.append((plugin_max, max_req_str))
            
            # 如果找到冲突，添加到冲突列表
            if conflict_found:
                conflicts.append(ConflictInfo(
                    dependency_name=dep_name,
                    conflicting_plugins=conflicting_plugins
                ))
        
        return conflicts
    
    def display_conflicts(self, conflicts: List[ConflictInfo]) -> None:
        """
        在控制台显示冲突信息
        
        Args:
            conflicts: 冲突信息列表
        """
        if not conflicts:
            print(f"{Fore.GREEN}未检测到依赖冲突。{Style.RESET_ALL}")
            return
        
        print(f"{Fore.RED}检测到 {len(conflicts)} 个依赖冲突：{Style.RESET_ALL}")
        
        for conflict in conflicts:
            print(f"\n{Fore.YELLOW}依赖: {conflict.dependency_name}{Style.RESET_ALL}")
            
            table_data = []
            for plugin, version_req in conflict.conflicting_plugins:
                table_data.append([plugin, version_req])
            
            print(tabulate(table_data, headers=["插件", "版本要求"], tablefmt="grid"))
    
    def generate_conflict_report(self, conflicts: List[ConflictInfo]) -> str:
        """
        生成冲突报告
        
        Args:
            conflicts: 冲突信息列表
            
        Returns:
            报告文件路径
        """
        report_file = self.output_dir / "conflict_report.md"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("# 依赖冲突报告\n\n")
                
                if not conflicts:
                    f.write("未检测到依赖冲突。\n")
                    return str(report_file)
                
                f.write(f"检测到 {len(conflicts)} 个依赖冲突：\n\n")
                
                for conflict in conflicts:
                    f.write(f"## 依赖: {conflict.dependency_name}\n\n")
                    
                    f.write("| 插件 | 版本要求 |\n")
                    f.write("|------|----------|\n")
                    
                    for plugin, version_req in conflict.conflicting_plugins:
                        f.write(f"| {plugin} | {version_req} |\n")
                    
                    f.write("\n")
            
            # 同时生成JSON格式的报告
            json_report_file = self.output_dir / "conflict_report.json"
            json_data = []
            
            for conflict in conflicts:
                conflict_data = {
                    "dependency_name": conflict.dependency_name,
                    "conflicting_plugins": [
                        {"plugin": plugin, "version_requirement": version_req}
                        for plugin, version_req in conflict.conflicting_plugins
                    ]
                }
                json_data.append(conflict_data)
            
            with open(json_report_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"冲突报告已生成: {report_file}")
            logger.info(f"JSON格式报告已生成: {json_report_file}")
            
            return str(report_file)
        except Exception as e:
            logger.error(f"生成报告时出错: {str(e)}")
            print(f"{Fore.RED}错误: 生成报告时出错: {str(e)}{Style.RESET_ALL}")
            return ""
    
    def replace_dependency(self, old_dep: str, new_dep: str) -> int:
        """
        替换依赖
        
        Args:
            old_dep: 原依赖信息
            new_dep: 新依赖信息
            
        Returns:
            替换的文件数量
        """
        logger.info(f"替换依赖: {old_dep} -> {new_dep}")
        
        # 解析原依赖信息
        old_dep_name = old_dep
        old_dep_version = ""
        
        # 检查是否包含版本信息
        if any(op in old_dep for op in ['==', '>=', '<=', '>', '<', '~=']):
            try:
                old_req = Requirement(old_dep)
                old_dep_name = old_req.name.lower()
                old_dep_version = str(old_req.specifier)
            except Exception as e:
                logger.error(f"无法解析原依赖信息: {old_dep}")
                logger.error(f"错误: {str(e)}")
                print(f"{Fore.RED}错误: 无法解析原依赖信息: {old_dep}{Style.RESET_ALL}")
                print(f"{Fore.RED}详细错误: {str(e)}{Style.RESET_ALL}")
                return 0
        else:
            old_dep_name = old_dep.lower()
        
        # 解析新依赖信息
        try:
            if any(op in new_dep for op in ['==', '>=', '<=', '>', '<', '~=']):
                new_req = Requirement(new_dep)
                new_dep_name = new_req.name
                new_dep_full = new_dep
            else:
                new_dep_name = new_dep
                new_dep_full = new_dep
        except Exception as e:
            logger.error(f"无法解析新依赖信息: {new_dep}")
            logger.error(f"错误: {str(e)}")
            print(f"{Fore.RED}错误: 无法解析新依赖信息: {new_dep}{Style.RESET_ALL}")
            print(f"{Fore.RED}详细错误: {str(e)}{Style.RESET_ALL}")
            return 0
        
        # 记录替换情况
        replaced_files = set()
        
        # 遍历插件目录
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            plugin_name = plugin_dir.name
            req_file = plugin_dir / "requirements.txt"
            
            if not req_file.exists():
                continue
            
            # 读取requirements.txt文件
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except Exception as e:
                logger.error(f"无法读取文件 {req_file}: {str(e)}")
                print(f"{Fore.RED}错误: 无法读取文件 {req_file}: {str(e)}{Style.RESET_ALL}")
                continue
            
            # 标记是否需要更新文件
            file_updated = False
            new_lines = []
            
            for line in lines:
                original_line = line
                line = line.strip()
                
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    new_lines.append(original_line)
                    continue
                
                try:
                    # 解析依赖
                    req = Requirement(line)
                    dep_name = req.name.lower()
                    dep_version = str(req.specifier)
                    
                    # 检查是否匹配替换条件
                    if dep_name == old_dep_name:
                        if not old_dep_version or dep_version == old_dep_version:
                            # 执行替换
                            new_lines.append(f"{new_dep_full}\n")
                            file_updated = True
                            logger.info(f"在插件 {plugin_name} 中替换: {line} -> {new_dep_full}")
                        else:
                            new_lines.append(original_line)
                    else:
                        new_lines.append(original_line)
                except Exception:
                    # 无法解析的行保持不变
                    new_lines.append(original_line)
            
            # 如果文件需要更新，写入新内容
            if file_updated:
                try:
                    with open(req_file, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    replaced_files.add(str(req_file))
                except Exception as e:
                    logger.error(f"无法写入文件 {req_file}: {str(e)}")
                    print(f"{Fore.RED}错误: 无法写入文件 {req_file}: {str(e)}{Style.RESET_ALL}")
        
        logger.info(f"依赖替换完成，共更新了 {len(replaced_files)} 个文件")
        return len(replaced_files)

def check_conflicts(plugins_dir: str) -> None:
    """
    检查依赖冲突
    
    Args:
        plugins_dir: 插件目录路径
    """
    try:
        resolver = DependencyResolver(plugins_dir)
        resolver.scan_plugins()
        conflicts = resolver.detect_conflicts()
        resolver.display_conflicts(conflicts)
        report_file = resolver.generate_conflict_report(conflicts)
        
        if report_file:
            print(f"\n冲突报告已生成: {report_file}")
    except Exception as e:
        print(f"{Fore.RED}错误: 检查依赖冲突时发生异常: {str(e)}{Style.RESET_ALL}")
        traceback.print_exc()

def replace_dependency(plugins_dir: str, old_dep: str, new_dep: str) -> None:
    """
    替换依赖
    
    Args:
        plugins_dir: 插件目录路径
        old_dep: 原依赖信息
        new_dep: 新依赖信息
    """
    try:
        resolver = DependencyResolver(plugins_dir)
        count = resolver.replace_dependency(old_dep, new_dep)
        
        if count > 0:
            print(f"{Fore.GREEN}依赖替换完成，共更新了 {count} 个文件{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}未找到匹配的依赖进行替换{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}错误: 替换依赖时发生异常: {str(e)}{Style.RESET_ALL}")
        traceback.print_exc()

def main():
    """主函数"""
    try:
        print(f"{Fore.CYAN}依赖冲突解决工具{Style.RESET_ALL}")
        print("=" * 50)
        
        # 检查命令行参数
        if len(sys.argv) < 2:
            print(f"{Fore.RED}错误: 未提供插件目录路径{Style.RESET_ALL}")
            print("用法: python dependency_resolver.py <插件目录路径> [操作] [参数...]")
            input("\n按回车键退出...")
            return
        
        # 获取插件目录路径
        plugins_dir = sys.argv[1]
        
        # 检查插件目录是否存在
        if not os.path.exists(plugins_dir):
            print(f"{Fore.RED}错误: 插件目录不存在: {plugins_dir}{Style.RESET_ALL}")
            input("\n按回车键退出...")
            return
        
        # 检查是否提供了操作选项
        operation = sys.argv[2] if len(sys.argv) > 2 else None
        
        if operation == "1":
            # 依赖冲突查询
            check_conflicts(plugins_dir)
        elif operation == "2":
            # 依赖替换
            if len(sys.argv) < 5:
                print(f"{Fore.RED}错误: 依赖替换需要提供原依赖和新依赖信息{Style.RESET_ALL}")
                input("\n按回车键退出...")
                return
            
            old_dep = sys.argv[3]
            new_dep = sys.argv[4]
            replace_dependency(plugins_dir, old_dep, new_dep)
        else:
            # 交互式菜单
            while True:
                print("\n请选择操作 (Please Select) :")
                print("1. 依赖冲突查询 (Check Conflicts) ")
                print("2. 依赖替换 (Replace Dependency) ")
                print("0. 退出 (Exit) ")
                
                try:
                    choice = input("\n请输入选项 (0-2): ").strip()
                    
                    if choice == '0':
                        print("退出程序")
                        break
                    elif choice == '1':
                        check_conflicts(plugins_dir)
                    elif choice == '2':
                        old_dep = input("请输入已有依赖信息 Enter Existing dependencies (例如: onnx 或 onnx>=0.5): ").strip()
                        new_dep = input("请输入新依赖信息 Enter New Dependencies (例如: onnx-weekly==0.5): ").strip()
                        
                        if old_dep and new_dep:
                            replace_dependency(plugins_dir, old_dep, new_dep)
                        else:
                            print(f"{Fore.RED}错误: 依赖信息不能为空{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}无效的选项，请重新输入{Style.RESET_ALL}")
                except KeyboardInterrupt:
                    print("\n操作被用户中断")
                    break
                except Exception as e:
                    print(f"{Fore.RED}发生错误: {str(e)}{Style.RESET_ALL}")
                    traceback.print_exc()
    except Exception as e:
        print(f"{Fore.RED}程序发生未处理的异常: {str(e)}{Style.RESET_ALL}")
        traceback.print_exc()
    finally:
        # 确保在命令行模式下不会立即退出
        if len(sys.argv) <= 2:
            input("\n按回车键退出...")

if __name__ == "__main__":
    main()
