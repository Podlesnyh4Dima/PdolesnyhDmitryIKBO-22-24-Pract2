import csv
import sys
import os
import json
from urllib.request import urlopen
from urllib.error import URLError
import graphviz
from collections import deque

CONFIG_SCHEMA = {
    'package_name': {'type': str, 'required': True, 'validator': lambda v: bool(v), 'error_msg': "Имя пакета не может быть пустым."},
    'repo_source': {'type': str, 'required': True, 'validator': lambda v: os.path.exists(v) or v.startswith('http'), 'error_msg': "URL репозитория должен быть корректным URL или существующим путем к файлу."},
    'repo_mode': {'type': str, 'required': True, 'validator': lambda v: v in ['real', 'test_file', 'test_url'], 'error_msg': "Режим работы должен быть 'real', 'test_file' или 'test_url'."},
    'package_version': {'type': str, 'required': True, 'validator': lambda v: any(c.isdigit() for c in v) or v == 'latest', 'error_msg': "Версия пакета должна содержать цифры или быть 'latest'."},
    'max_depth': {'type': int, 'required': True, 'validator': lambda v: 0 <= v <= 10, 'error_msg': "Максимальная глубина должна быть целым числом от 0 до 10."},
    'filter_substring': {'type': str, 'required': False, 'default': '', 'validator': lambda v: True, 'error_msg': ""},
}


def load_and_validate_config(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Ошибка: Конфигурационный файл '{file_path}' не найден.")

    config = {}
    try:
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) == 2:
                    key = row[0].strip()
                    value = row[1].strip()
                    config[key] = value
    except Exception as e:
        raise ValueError(f"Ошибка при чтении CSV-файла: {e}")

    validated_config = {}
    for key, schema in CONFIG_SCHEMA.items():
        raw_value = config.get(key, schema.get('default', ''))
        
        if key == 'repo_source' and config.get('repo_mode') == 'test_file':
            validated_config[key] = raw_value
            continue

        if schema['required'] and not raw_value:
            if 'default' not in schema:
                raise ValueError(f"Ошибка параметра '{key}': Обязательный параметр отсутствует.")
            
        value = raw_value
        
        if schema.get('type') == int and raw_value:
            try:    
                value = int(value)
            except ValueError:
                raise ValueError(f"Ошибка параметра '{key}': Ожидался тип int, получено '{raw_value}'.")
        
        if schema['type'] == str and not value and 'default' in schema:
             value = schema['default']

        if not schema['validator'](value):
            raise ValueError(f"Ошибка параметра '{key}': {schema['error_msg']}")
            
        validated_config[key] = value
    return validated_config

def fetch_package_data_npm(package_name, repo_base_url):
    url = f"{repo_base_url.rstrip('/')}/{package_name}"
    try:
        with urlopen(url) as response:
            data = json.load(response)
        return data
    except URLError as e:
        print(f"Не удалось загрузить данные для '{package_name}' по URL {url}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Некорректный JSON в ответе от {url}: {e}")
        return None


def get_direct_dependencies_npm(package_data, version_spec='latest'):
    if not package_data:
        return {}

    version_to_fetch = None

    if version_spec == 'latest':
        if 'dist-tags' in package_data and 'latest' in package_data['dist-tags']:
            version_to_fetch = package_data['dist-tags']['latest']
        else:
            if 'versions' and package_data['versions']:
                version_to_fetch = list(package_data['versions'].keys())[-1]
            else:
                return {}
    
    elif version_spec in package_data.get('versions', {}):
        version_to_fetch = version_spec
    
    else:
        if 'dist-tags' in package_data and 'latest' in package_data['dist-tags']:
            version_to_fetch = package_data['dist-tags']['latest']
        elif 'versions':
             version_to_fetch = list(package_data['versions'].keys())[-1]

    if not version_to_fetch or version_to_fetch not in package_data.get('versions', {}):
        return {}

    version_data = package_data['versions'][version_to_fetch]
    dependencies = version_data.get('dependencies', {})
    return dependencies

def fetch_dependencies(package_name, version_spec, params):
    
    if params['repo_mode'] == 'real':
        package_data = fetch_package_data_npm(package_name, params['repo_source'])
        return get_direct_dependencies_npm(package_data, version_spec)
    
    elif params['repo_mode'] == 'test_file':
        if not hasattr(fetch_dependencies, 'test_graph'):
            try:
                with open(params['repo_source'], 'r', encoding='utf-8') as f:
                    fetch_dependencies.test_graph = json.load(f)
            except Exception as e:
                raise RuntimeError(f"Не удалось загрузить тестовый файл графа '{params['repo_source']}': {e}")
        
        deps_list = fetch_dependencies.test_graph.get(package_name, [])
        return {dep: 'test_ver' for dep in deps_list}
    
    elif params['repo_mode'] == 'test_url':
        raise NotImplementedError("Режим 'test_url' не поддерживается для рекурсивного обхода")
    
    return {}


def build_dependency_graph_dfs(
    package_name, 
    version_spec, 
    params, 
    graph, 
    viz_graph, 
    current_depth, 
    visited, 
    resolved_packages
):

    filter_sub = params['filter_substring']
    if filter_sub and filter_sub in package_name:
        return

    viz_graph.node(package_name)

    if package_name in visited:
        return

    if current_depth >= params['max_depth']:
        return
        
    if package_name in resolved_packages:
        return
        
    visited.add(package_name)
    if package_name not in graph:
        graph[package_name] = set()

    try:
        dependencies = fetch_dependencies(package_name, version_spec, params)
    except Exception as e:
        print(f"Не удалось получить зависимости для {package_name}: {e}")
        dependencies = {}

    for dep_name, dep_version_spec in dependencies.items():
        graph[package_name].add(dep_name)
        viz_graph.edge(package_name, dep_name)
        
        build_dependency_graph_dfs(
            dep_name, 
            dep_version_spec, 
            params, 
            graph, 
            viz_graph, 
            current_depth + 1, 
            visited, 
            resolved_packages
        )

    visited.remove(package_name)
    resolved_packages.add(package_name)


def _dfs_sort(node, graph, visited, recursion_stack, load_order):
    if node not in graph:
        if node not in visited:
             load_order.appendleft(node)
        visited.add(node)
        return

    visited.add(node)
    recursion_stack.add(node)

    for dependency in graph[node]:
        if dependency not in visited:
            _dfs_sort(dependency, graph, visited, recursion_stack, load_order)
        elif dependency in recursion_stack:
            raise ValueError(f"Обнаружен цикл! Зависимость {node} -> {dependency} не может быть разрешена.")

    recursion_stack.remove(node)
    load_order.appendleft(node)


def get_dependency_load_order(start_node, graph):
    
    all_nodes = set(graph.keys())
    for deps in graph.values():
        all_nodes.update(deps)
    
    if start_node not in all_nodes:
        print(f"Ошибка: Стартовый пакет '{start_node}' не найден в построенном графе.")
        return []

    load_order = deque()
    visited = set()
    recursion_stack = set()

    try:
        _dfs_sort(start_node, graph, visited, recursion_stack, load_order)
    except ValueError as e:
        print(f"Ошибка: {e}")
        return []

    return list(load_order)


def main():
    CONFIG_FILE = 'config.csv'

    try:
        params = load_and_validate_config(CONFIG_FILE)

        if params['repo_mode'] == 'test_file':
            try:
                test_file_name = input("Введите имя JSON-файла для тестового графа: ")
                
                if not os.path.exists(test_file_name):
                    raise FileNotFoundError(f"Файл '{test_file_name}' не найден в текущей директории.")
                
                params['repo_source'] = test_file_name
                
                test_pkg_name = input("Введите имя стартового пакета: ")
                if not test_pkg_name:
                     raise ValueError("Имя стартового пакета не может быть пустым.")
                params['package_name'] = test_pkg_name
            
            except (FileNotFoundError, ValueError, EOFError) as e:
                print(f"\n{e}")
                print("\nЗавершение работы из-за ошибки.")
                sys.exit(1)
            except KeyboardInterrupt:
                print("\n\nВвод отменен. Завершение работы.")
                sys.exit(1)


        key_map = {
            'package_name': 'Имя анализируемого пакета',
            'repo_source': 'URL/Путь репозитория',
            'repo_mode': 'Режим работы репозитория',
            'package_version': 'Версия пакета',
            'max_depth': 'Максимальная глубина анализа',
            'filter_substring': 'Подстрока для фильтрации'
        }
        for key, value in params.items():
            print(f"  {key_map.get(key, key)}: {value}")


        graph_adj_list = {}
        visited_path = set()
        resolved_nodes = set()
        
        viz_graph = graphviz.Digraph(comment=f"Граф зависимостей для {params['package_name']}")

        viz_graph.attr(rankdir='TB', size='10,15') 

        viz_graph.node_attr.update(
            color='lightblue2', 
            style='filled', 
            shape='box', 
            fontsize='14' 
        )
        viz_graph.edge_attr.update(arrowsize='0.8')

        build_dependency_graph_dfs(
            params['package_name'],
            params['package_version'],
            params,
            graph_adj_list,
            viz_graph,
            current_depth=0,
            visited=visited_path,
            resolved_packages=resolved_nodes
        )
        
        printable_graph = {k: list(v) for k, v in graph_adj_list.items()}
        print(printable_graph)


        load_order = get_dependency_load_order(params['package_name'], graph_adj_list)
        if load_order:
            print(" -> ".join(load_order))


        output_filename = 'dependency_graph'
        try:
            viz_graph.render(output_filename, view=False, format='png', cleanup=True)
            print(f"\n[Info] Граф визуализирован в файл '{output_filename}.png'")

        except Exception as e:
            print(f"\nНе удалось сгенерировать изображение графа: {e}")


    except (FileNotFoundError, ValueError, RuntimeError, NotImplementedError) as e:
        print(f"\n{e}")
        print("\nЗавершение работы из-за ошибки.")
        sys.exit(1)
    except Exception as e:
        print(f"\nНеизвестная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()