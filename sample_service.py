import os
import json
import uuid

class SampleService:
    def __init__(self):
        # Store the samples.json file in the user's home directory
        self.data_path = os.path.join(os.path.expanduser("~"), ".labscribe_samples.json")
        self.samples = self._load_samples()

    def _load_samples(self):
        """Loads samples from the JSON file. Returns an empty list if the file doesn't exist."""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_samples(self):
        """Saves the current list of samples to the JSON file."""
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self.samples, f, indent=4)

    def get_samples(self):
        """Returns a list of all samples."""
        return self.samples

    def add_sample(self, sample_data):
        """
        Adds a new sample to the list.
        Args:
            sample_data (dict): A dictionary containing the sample's properties.
        Returns:
            dict: The newly created sample with a unique ID.
        """
        sample_data['id'] = str(uuid.uuid4())
        self.samples.append(sample_data)
        self._save_samples()
        return sample_data

    def update_sample(self, sample_id, updated_data):
        """
        Updates an existing sample.
        Args:
            sample_id (str): The ID of the sample to update.
            updated_data (dict): A dictionary with the updated properties.
        Returns:
            bool: True if the update was successful, False otherwise.
        """
        for i, sample in enumerate(self.samples):
            if sample.get('id') == sample_id:
                # Make sure the ID is not changed
                updated_data['id'] = sample_id
                self.samples[i] = updated_data
                self._save_samples()
                return True
        return False

    def delete_sample(self, sample_id):
        """
        Deletes a sample from the list.
        Args:
            sample_id (str): The ID of the sample to delete.
        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        initial_len = len(self.samples)
        self.samples = [s for s in self.samples if s.get('id') != sample_id]
        if len(self.samples) < initial_len:
            self._save_samples()
            return True
        return False
