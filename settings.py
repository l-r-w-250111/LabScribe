import json
import os

class Settings:
    def __init__(self, file_path='settings.json'):
        self.file_path = file_path
        self.defaults = {
            'username': 'Default User',
            'save_folder': os.path.join(os.path.expanduser('~'), 'ELN_Notes'),
            'use_tsa': False,
            'tsa_url': 'https://freetsa.org/tsr'
        }
        self.data = self.defaults.copy()
        self.load()

    def load(self):
        """Loads settings from the JSON file."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                self.data.update(file_data)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is empty/corrupt, save defaults
            self.save()

    def save(self):
        """Saves the current settings to the JSON file."""
        # Ensure the save folder exists before saving settings
        save_folder = self.get('save_folder')
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
            
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def get(self, key):
        """Gets a setting value by key."""
        return self.data.get(key, self.defaults.get(key))

    def set(self, key, value):
        """Sets a setting value by key and saves it."""
        self.data[key] = value
        self.save()

if __name__ == '__main__':
    # Example usage
    settings = Settings()
    print(f"Current username: {settings.get('username')}")
    print(f"Current save folder: {settings.get('save_folder')}")
    
    # settings.set('username', 'Kazu')
    # settings.set('save_folder', 'C:\My_Notes')
    
    # print(f"Updated username: {settings.get('username')}")
    # print(f"Updated save folder: {settings.get('save_folder')}")
