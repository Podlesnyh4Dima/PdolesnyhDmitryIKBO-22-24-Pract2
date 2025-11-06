import csv
import sys
import os
import json
from urllib.request import urlopen
from urllib.error import URLError


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
        raw_value = config.get(key, '')
        if schema['required'] and not raw_value:
            raise ValueError(f"Ошибка параметра '{key}': Обязательный параметр отсутствует.")
        value = raw_value
        if value:
            try:
                if schema['type'] == int:
                    value = int(value)
            except ValueError:
                raise ValueError(f"Ошибка параметра '{key}': Ожидался тип {schema['type'].__name__}, получено '{raw_value}'.")
        if value and not schema['validator'](value):
            raise ValueError(f"Ошибка параметра '{key}': {schema['error_msg']}")
        if not raw_value and 'default' in schema:
            value = schema['default']
        validated_config[key] = value
    return validated_config


def fetch_package_data_npm(package_name, repo_base_url):
    """Получает JSON-данные пакета из npm-совместимого репозитория."""
    url = f"{repo_base_url.rstrip('/')}/{package_name}"
    try:
        with urlopen(url) as response:
            data = json.load(response)
        return data
    except URLError as e:
        raise RuntimeError(f"Не удалось загрузить данные пакета '{package_name}' по URL {url}: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Некорректный JSON в ответе от {url}: {e}")


def get_direct_dependencies_npm(package_data, version='latest'):
    """Извлекает прямые зависимости из npm-формата."""
    if version == 'latest':
        if 'dist-tags' not in package_data or 'latest' not in package_data['dist-tags']:
            raise ValueError("Версия 'latest' не указана в dist-tags.")
        version = package_data['dist-tags']['latest']

    if 'versions' not in package_data or version not in package_data['versions']:
        raise ValueError(f"Версия '{version}' не найдена в данных пакета.")

    version_data = package_data['versions'][version]
    dependencies = version_data.get('dependencies', {})
    return dependencies


def main():
    CONFIG_FILE = 'config.csv'

    try:
        params = load_and_validate_config(CONFIG_FILE)

        # Вывод параметров (Этап 1)
        key_map = {
            'package_name': 'Имя анализируемого пакета',
            'repo_source': 'URL/Путь репозитория',
            'repo_mode': 'Режим работы репозитория',
            'package_version': 'Версия пакета',
            'max_depth': 'Максимальная глубина анализа',
            'filter_substring': 'Подстрока для фильтрации'
        }
        print("Загруженные параметры конфигурации:")
        for key, value in params.items():
            print(f"  {key_map.get(key, key)}: {value}")

        # === Этап 2: сбор прямых зависимостей ===
        package_name = params['package_name']
        repo_source = params['repo_source']
        repo_mode = params['repo_mode']
        version = params['package_version']

        if repo_mode == 'test_url':
            # repo_source — полный URL к JSON-файлу
            package_url = repo_source
            try:
                with urlopen(package_url) as resp:
                    package_data = json.load(resp)
            except Exception as e:
                raise RuntimeError(f"Ошибка при загрузке тестового JSON: {e}")
        elif repo_mode == 'real':
            # repo_source — базовый URL (например, https://registry.npmjs.org/)
            package_data = fetch_package_data_npm(package_name, repo_source)
        else:
            raise NotImplementedError("Режим 'test_file' не поддерживается на Этапе 2.")

        dependencies = get_direct_dependencies_npm(package_data, version)

        print("\nПрямые зависимости пакета:")
        if dependencies:
            for dep, ver in dependencies.items():
                print(f"  {dep}: {ver}")
        else:
            print("  Зависимости отсутствуют.")

    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"\n{e}")
        print("\nЗавершение работы из-за ошибки.")
        sys.exit(1)
    except Exception as e:
        print(f"\nНеизвестная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()