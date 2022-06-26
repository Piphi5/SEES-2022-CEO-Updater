from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from collections import namedtuple
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import sys
import shutil
import datetime
import pandas as pd
import time
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

raw_storage_dir = "SEES-2022-CEO-Data"
ago_storage_dir = "CEO Output"

def combine_csvs(directory, project_ids):
    while len(os.listdir(temp_dir)) < len(project_ids) or not all([csv.endswith(".csv") for csv in os.listdir(temp_dir)]):
        time.sleep(1)
    df = pd.DataFrame()
    for csv in os.listdir(directory):
        temp = pd.read_csv(os.path.join(directory,csv))
        df = df.append(temp, ignore_index=True)
    return df

def download_csvs(driver, prefix, project_ids):
    for project in project_ids:
        driver.get(f"{prefix}?projectId={project}")

def process_df(df, output_path):
    df = df[df["email"].notna()]
    df = df.drop("email", axis=1)
    df["AOI Number"] = df["plotid"] // 100
    df.to_csv(output_path)


def handle_sampling_unit(driver, sampling_unit, temp_dir, project_ids):
    date_str = datetime.datetime.today().strftime("%Y-%m-%d")
    output_file =  f"{raw_storage_dir}/{sampling_unit.output_directory}/{sampling_unit.output_prefix}-{date_str}.csv"
    os.mkdir(temp_dir)
    try:
      download_csvs(driver, sampling_unit.ceo_prefix, project_ids)
      df = combine_csvs(temp_dir, project_ids)
      process_df(df,output_file)
    finally:
      shutil.rmtree(temp_dir)
      return output_file

def upload_to_ago(gis, itemid, filename):
  item = gis.content.get(itemid)
  item_layer_collection = FeatureLayerCollection.fromitem(item)
  response = item_layer_collection.manager.overwrite(
      os.path.join(os.getcwd(), filename)
  )

  return response["success"]

email = sys.argv[1]
password = sys.argv[2]

ago_username = sys.argv[3]
ago_password = sys.argv[4]

for directory in [raw_storage_dir, ago_storage_dir]:
  if not os.path.exists(directory):
    os.mkdir(directory)


project_ids = [31343, 31344, 31345, 31346, 31347, 31364, 31365, 31383, 31422]
SamplingUnit = namedtuple("SamplingUnit",  "ceo_prefix output_directory output_prefix itemid")
psu = SamplingUnit(ceo_prefix="https://collect.earth/dump-project-aggregate-data", output_directory="PSU", output_prefix="SEES2022-CEO-PSU", itemid = "e185caf63fbd452aa7b3d1e6396404a9")
ssu = SamplingUnit(ceo_prefix="https://collect.earth/dump-project-raw-data", output_directory="SSU", output_prefix="SEES2022-CEO-SSU", itemid = "543d31deb07c4a4ab4ae9d59b429508d")

temp_dir = os.path.join(os.getcwd(), "Temp")
options = webdriver.ChromeOptions()
prefs = {"download.default_directory": temp_dir}
options.add_experimental_option("prefs",prefs)
driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
driver.get("https://collect.earth/login?returnurl=%2Fhome")

element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "password"))
    )

email_form = driver.find_element(By.ID, "email")
password_form = driver.find_element(By.ID, "password")
submit = driver.find_element(By.XPATH, "//button[@type='submit']")

email_form.send_keys(email)
password_form.send_keys(password)
submit.click()

time.sleep(1)

psu_file = handle_sampling_unit(driver, psu, temp_dir, project_ids)
ssu_file = handle_sampling_unit(driver, ssu, temp_dir, project_ids)
driver.quit()

gis = GIS(
            url="https://igestrategies.maps.arcgis.com",
            username=ago_username,
            password=ago_password,
        )

psu_ago_file = f"{ago_storage_dir}/{psu.output_prefix}.csv"
ssu_ago_file = f"{ago_storage_dir}/{ssu.output_prefix}.csv"

shutil.copy(psu_file, psu_ago_file)
shutil.copy(ssu_file, ssu_ago_file)


psu_status = upload_to_ago(gis, psu.itemid, psu_ago_file)
ssu_status = upload_to_ago(gis, ssu.itemid, ssu_ago_file)

if not (psu_status and ssu_status):
  raise Exception("Failed to upload to ArcGIS")
