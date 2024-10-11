import hashlib

class MD5Generator:
    def __init__(self, input_json, delimiter):
        self.input_json = input_json
        self.delimiter = delimiter
        self.generate_md5_hash()

    def exclude_keys(self, keys_to_exclude):
        return {k: v for k, v in self.input_json.items() if k not in keys_to_exclude}

    def sort_keys_and_values(self, obj):
        if isinstance(obj, list):
            return [self.sort_keys_and_values(elem) for elem in obj]
        if isinstance(obj, dict):
            sorted_dict = {}
            for key, value in sorted(obj.items(), key=lambda item: str(item)):
                sorted_dict[key] = self.sort_keys_and_values(value)
            return sorted_dict
        return obj

    def concatenate_keys_and_values(self, obj, delimiter):
        if isinstance(obj, list):
            return delimiter.join(self.concatenate_keys_and_values(elem, delimiter) for elem in obj)
        if isinstance(obj, dict):
            return delimiter.join(f'{k}{delimiter}{self.concatenate_keys_and_values(v, delimiter)}' for k, v in obj.items())
        return str(obj)

    def generate_md5_hash(self):
        keys_to_exclude = ['dateStart', 'dateEnd']
        filtered_json = self.exclude_keys(keys_to_exclude)
        sorted_json = self.sort_keys_and_values(filtered_json)
        concatenated_str = self.concatenate_keys_and_values(sorted_json, self.delimiter)
        trimmed_str = concatenated_str.replace(" ", "")
        lowercase_str = trimmed_str.lower()
        self.query_id = hashlib.md5(lowercase_str.encode()).hexdigest()
        print("Query ID:", self.query_id)