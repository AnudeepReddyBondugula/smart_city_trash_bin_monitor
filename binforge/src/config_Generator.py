import yaml
import random
import colorama
from datetime import datetime, timedelta

class Bin_Generator_Config:

    def __init__(self, num_wards: int, bins_per_ward: int, area_type_weights=None, status_weights=None):
        
        self.num_wards = num_wards
        self.bins_per_ward = bins_per_ward
        self.output_file = "bin_config.yaml"

        # default weights
        self.area_types = ["residential", "commercial", "industrial"]
        self.area_type_weights = area_type_weights or [0.7, 0.2, 0.1]

        # default weights
        self.statuses = ["active", "maintenance"]
        self.status_weights = status_weights or [0.9, 0.1]

        # to track used coordinates
        self.used_coordinates_set = set()

    def generate_unique_coordinates(self, base_lat, base_long):

        while True:
            latitude = round(base_lat + random.uniform(-0.01, 0.01), 6)
            longitude = round(base_long + random.uniform(-0.01, 0.01), 6)
            if (latitude, longitude) not in self.used_coordinates_set:
                self.used_coordinates_set.add((latitude, longitude))
                return latitude, longitude

    def generate_yaml_config(self):
        
        wards = []
        base_lat, base_long = 17.323108, 78.541517  # starting coordinates
        for w in range(1, self.num_wards + 1):
            ward = {
                "ward_id": w,
                "ward_name": f"Ward-{w:02d}",
                "area_type": random.choices(self.area_types, weights=self.area_type_weights, k=1)[0],
                "bins": []
            }

            for b in range(1, self.bins_per_ward + 1):
                bin_id = f"B{w:02d}{b:02d}"
                latitude, longitude = self.generate_unique_coordinates(base_lat, base_long)
                latitude = round(base_lat + (w * 0.005) + (b * 0.0005), 6)
                longitude = round(base_long + (w * 0.005) + (b * 0.0005), 6)
                install_date = (datetime(2025, 1, 10) + timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d")
                status = random.choices(self.statuses, weights=self.status_weights, k=1)[0]

                ward["bins"].append({
                    "bin_id": bin_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    "installed_at": install_date,
                    "status": status
                })
            wards.append(ward)
        config = {"wards": wards}

        try:
            # Write to YAML file
            with open(self.output_file, "w") as f:
                yaml.dump(config, f, sort_keys=False)

            print(colorama.Fore.GREEN + f"Configuration file '{self.output_file}' generated successfully."
                + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"Error generating configuration file: {e}" + colorama.Style.RESET_ALL)

if __name__ == "__main__":

    num_wards = int(input(colorama.Fore.YELLOW + "Enter number of wards: " + colorama.Style.RESET_ALL))
    bins_per_ward = int(input(colorama.Fore.YELLOW + "Enter number of bins per ward: " + colorama.Style.RESET_ALL))

    obj = Bin_Generator_Config(num_wards, bins_per_ward, area_type_weights=[0.7, 0.2, 0.1], status_weights=[0.9, 0.1])
    obj.generate_yaml_config()
