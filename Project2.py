import csv
import sys
import os

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

if __name__ == "__main__":
    CONFIG_FILE = 'config.csv'

    try:
        params = load_and_validate_config(CONFIG_FILE)
        
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
            
    except (FileNotFoundError, ValueError) as e:
        print(f"\n{e}")
        print("\nЗавершение работы из-за ошибки конфигурации.")
        sys.exit(1)
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")
        sys.exit(1)