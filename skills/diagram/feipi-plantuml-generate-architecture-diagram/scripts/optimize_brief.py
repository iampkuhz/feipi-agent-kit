#!/usr/bin/env python3
"""
Architecture Diagram Brief 优化脚本

本脚本负责在 PlantUML 生成前对 brief.yaml 进行布局优化，属于画法层面的处理，
而非领域定义内容的修改。

优化项包括：
1. Layer ID 简短化（连字符 -> 下划线/简短单词）
2. Package 描述格式化（长描述按逗号分割为多行）
3. 同域组件排序（按视觉权重：actor > component > database > cloud）
4. hidden_lines 生成（同 layer 组件数 >= 2 时自动生成对齐线配置）
5. include_legend 默认值为 false

用法:
    python optimize_brief.py <input_brief.yaml> [output_brief.yaml]

如果未指定 output，默认输出到 input 的同名 .optimized.yaml 文件
"""

import sys
import yaml
from pathlib import Path
from typing import Any


# Layer ID 映射表：连字符长名 -> 简短单词
LAYER_ID_MAPPING = {
    'user-agent': 'user_as',
    'user_ctrl': 'user_as',
    'agent-ctrl': 'agent_as',
    'ap2-protocol': 'protocol',
    'ap2-protocol-domain': 'protocol',
    'protocol-domain': 'protocol',
    'external': 'ext_sys',
    'external-system': 'ext_sys',
    'external-system-domain': 'ext_sys',
    'external-domain': 'ext_sys',
    'blockchain': 'chain',
    'blockchain-network': 'chain',
    'user': 'user_as',
    'service': 'svc',
}

# 组件视觉权重：越小越靠前（放中央）
COMPONENT_WEIGHT = {
    'actor': 1,
    'component': 2,
    'database': 3,
    'cloud': 4,
    'boundary': 5,
    'participant': 2,
}


def shorten_layer_id(layer_id: str) -> str:
    """将 layer ID 转换为简短形式"""
    # 先尝试精确匹配
    if layer_id in LAYER_ID_MAPPING:
        return LAYER_ID_MAPPING[layer_id]

    # 尝试将连字符转为下划线
    if '-' in layer_id:
        shortened = layer_id.replace('-', '_')
        # 如果转换后的 ID 不在映射表中，返回转换结果
        return shortened

    # 已经是简短形式，直接返回
    return layer_id


def format_description(description: str) -> str:
    """将长描述按中文逗号、顿号分割为多行"""
    if not description:
        return description

    # 按中文逗号、顿号分割
    parts = description.replace('，', '\n').replace('、', '\n').replace(',', '\n')
    return parts


def sort_components(components: list) -> list:
    """按视觉权重排序组件"""
    def get_weight(comp: dict) -> int:
        comp_type = comp.get('type', 'component')
        return COMPONENT_WEIGHT.get(comp_type, 99)

    return sorted(components, key=get_weight)


def generate_hidden_lines(layer_id: str, components: list) -> list:
    """
    当同 layer 内组件数 >= 2 时，生成 hidden_lines 配置

    hidden_lines 用于在 PlantUML 中强制组件对齐，避免扁宽或瘦高
    """
    if len(components) < 2:
        return []

    hidden_lines = []
    # 生成相邻组件之间的 hidden 线
    for i in range(len(components) - 1):
        hidden_lines.append({
            'from': components[i]['id'],
            'to': components[i + 1]['id'],
            'direction': 'down',  # 默认垂直对齐
            'style': 'hidden',
        })

    return hidden_lines


def optimize_brief(brief: dict) -> dict:
    """
    对 brief 进行完整优化

    优化流程：
    1. Layer ID 简短化
    2. Component layer 引用同步
    3. Package 描述格式化
    4. 同域组件排序
    5. hidden_lines 生成
    6. include_legend 默认 false
    """
    optimized = brief.copy()

    # 1. Layer ID 简短化
    layer_id_map = {}  # 旧 ID -> 新 ID
    if 'layers' in optimized:
        new_layers = []
        for layer in optimized['layers']:
            old_id = layer.get('id', '')
            new_id = shorten_layer_id(old_id)
            layer_id_map[old_id] = new_id

            new_layer = layer.copy()
            new_layer['id'] = new_id

            # 2. Package 描述格式化
            if 'description' in new_layer:
                new_layer['description'] = format_description(new_layer['description'])

            new_layers.append(new_layer)

        optimized['layers'] = new_layers

    # 3. Component 的 layer 引用同步 + 同域组件排序
    if 'components' in optimized:
        # 按 layer 分组
        from collections import defaultdict
        components_by_layer = defaultdict(list)

        for comp in optimized['components']:
            new_comp = comp.copy()
            # 同步 layer 引用
            old_layer = comp.get('layer', '')
            if old_layer in layer_id_map:
                new_comp['layer'] = layer_id_map[old_layer]

            new_layer = new_comp.get('layer', '')
            components_by_layer[new_layer].append(new_comp)

        # 对每个 layer 内的组件排序
        sorted_components = []
        for layer_id in layer_id_map.values():
            if layer_id in components_by_layer:
                sorted_comps = sort_components(components_by_layer[layer_id])
                sorted_components.extend(sorted_comps)

        optimized['components'] = sorted_components

    # 4. hidden_lines 生成
    if 'layers' in optimized and 'hidden_lines' not in optimized:
        all_hidden_lines = []
        for layer in optimized['layers']:
            layer_id = layer['id']
            # 找到该 layer 的所有组件
            layer_components = [c for c in optimized.get('components', [])
                               if c.get('layer') == layer_id]
            hidden = generate_hidden_lines(layer_id, layer_components)
            all_hidden_lines.extend(hidden)

        if all_hidden_lines:
            optimized['hidden_lines'] = all_hidden_lines

    # 5. include_legend 默认 false
    if 'layout' not in optimized:
        optimized['layout'] = {}

    if 'include_legend' not in optimized['layout']:
        optimized['layout']['include_legend'] = False

    return optimized


def main():
    if len(sys.argv) < 2:
        print("用法：python optimize_brief.py <input_brief.yaml> [output_brief.yaml]")
        print("\n优化项:")
        print("  1. Layer ID 简短化")
        print("  2. Package 描述格式化")
        print("  3. 同域组件排序")
        print("  4. hidden_lines 生成")
        print("  5. include_legend 默认 false")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"错误：输入文件不存在：{input_path}")
        sys.exit(1)

    # 确定输出路径
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_name(input_path.stem + '.optimized.yaml')

    # 读取 brief
    with open(input_path, 'r', encoding='utf-8') as f:
        brief = yaml.safe_load(f)

    # 优化
    optimized = optimize_brief(brief)

    # 输出
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(optimized, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"优化完成：{output_path}")

    # 输出优化摘要
    print("\n优化摘要:")
    if 'layers' in optimized:
        print(f"  - Layer 数量：{len(optimized['layers'])}")
    if 'components' in optimized:
        print(f"  - Component 数量：{len(optimized['components'])}")
    if 'hidden_lines' in optimized:
        print(f"  - hidden_lines 数量：{len(optimized['hidden_lines'])}")
    print(f"  - include_legend: {optimized.get('layout', {}).get('include_legend', False)}")


if __name__ == '__main__':
    main()
