import os
import yaml
import pytest
from src.config_Generator import Bin_Generator_Config


@pytest.fixture
def config_file(tmp_path):
    output_file = tmp_path / "test_config.yaml"
    obj = Bin_Generator_Config(num_wards=5, bins_per_ward=4, area_type_weights=[0.7, 0.2, 0.1], status_weights=[0.9, 0.1])
    obj.output_file = str(output_file)
    obj.generate_yaml_config()
    return output_file


def test_file_created(config_file):
    assert os.path.exists(config_file)


def test_yaml_structure(config_file):
    with open(config_file) as f:
        data = yaml.safe_load(f)

    assert "wards" in data
    assert isinstance(data["wards"], list)

    ward = data["wards"][0]
    assert "ward_id" in ward
    assert "ward_name" in ward
    assert "area_type" in ward
    assert "bins" in ward
    assert isinstance(ward["bins"], list)

    bin_ = ward["bins"][0]
    assert "bin_id" in bin_
    assert "latitude" in bin_
    assert "longitude" in bin_
    assert "installed_at" in bin_
    assert "status" in bin_


def test_unique_coordinates(config_file):
    with open(config_file) as f:
        data = yaml.safe_load(f)

    coords = set()
    for ward in data["wards"]:
        for bin_ in ward["bins"]:
            coord = (bin_["latitude"], bin_["longitude"])
            assert coord not in coords
            coords.add(coord)