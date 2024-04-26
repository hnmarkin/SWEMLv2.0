import numpy as np
import pandas as pd
import ee #pip install earthengine-api
import EE_funcs
import os
from tqdm import tqdm
import concurrent.futures as cf
ee.Authenticate()
ee.Initialize()
import warnings
warnings.filterwarnings("ignore")

HOME = os.path.expanduser('~')

def GetSeasonalAccumulatedPrecipSingleSite(args):
    #get function inputs
    precip, output_res, lat, lon, Precippath, cell_id, year, dates = args

    #unit conversions and temporal frequency
    temporal_resample = 'D'
    kgm2_to_cm = 0.1

    # Gett lat/long from meta file
    poi = ee.Geometry.Point(lon, lat)

    #Get precipitation
    precip_poi = precip.getRegion(poi, output_res).getInfo()
    site_precip = EE_funcs.ee_array_to_df(precip_poi,['total_precipitation'])

    #Precipitation
    site_precip.set_index('datetime', inplace = True)
    site_precip = site_precip.resample(temporal_resample).sum()
    site_precip.reset_index(inplace = True)

    #make columns for inches
    site_precip['total_precipitation'] = site_precip['total_precipitation']*kgm2_to_cm
    site_precip.rename(columns={'total_precipitation':'daily_precipitation_cm'}, inplace = True)

    #get seasonal accumulated precipitation for site
    site_precip['season_precip'] = site_precip['daily_precipitation_cm'].cumsum()

    #be aware of file storage, save only dates lining up with ASO obs
    mask = site_precip['datetime'].isin(dates)
    site_precip = site_precip[mask].reset_index(drop = True)

    #subset to only dates with obs to reduce file size
    mask = site_precip['datetime'].isin(dates)
    site_precip = site_precip[mask].reset_index(drop = True)

    site_precip.to_csv(f"{Precippath}/{cell_id}.parquet")  #hdf or pkl these in a separate step?

    # with pd.HDFStore( f"{Precippath}/WY{str(year)}.h5", complevel=9, complib='zlib') as store:
    #     store[cell_id] = site_precip

    

def get_precip_threaded(year, region, output_res):
    #  #ASO file path
    aso_swe_files_folder_path = f"{HOME}/SWEMLv2.0/data/ASO/{output_res}M_SWE_csv/{region}"
    #make directory for data 
    Precippath = f"{HOME}/SWEMLv2.0/data/Precipitation/{region}/{output_res}M_NLDAS_Precip/{year}"
    if not os.path.exists(Precippath):
        os.makedirs(Precippath, exist_ok=True)
    
    #load metadata and get site info
    path = f"{HOME}/SWEMLv2.0/data/TrainingDFs/{region}/{region}_metadata.parquet"
    meta = pd.read_csv(path)
    
    #set water year start/end dates based on ASO flights for the end date
    print(f"Getting date information from observations for WY{year}")
    aso_swe_files = []
    for aso_swe_file in os.listdir(aso_swe_files_folder_path):  #add file names to aso_swe_files
        aso_swe_files.append(aso_swe_file)

    startdate = f"{year-1}-10-01"
    #search for files for water year and get last date, this works because no ASO obs in sep, oct, nov, dec
    files = [x for x in aso_swe_files if str(year) in x]
    dates = []
    for file in files:
        month = file[-8:-6]
        day = file[-6:-4]
        enddate = f"{str(year)}-{month}-{day}"
        dates.append(enddate)
    enddate = dates[-1]

    #NLDAS precipitation
    precip = ee.ImageCollection('NASA/NLDAS/FORA0125_H002').select('total_precipitation').filterDate(startdate, enddate)

    nsites = len(meta) #change this to all sites when ready
    print(f"Getting daily precipitation data for {nsites} sites")
    with cf.ThreadPoolExecutor(max_workers=None) as executor:
        {executor.submit(GetSeasonalAccumulatedPrecipSingleSite, (precip, output_res, meta.iloc[i]['cen_lat'], meta.iloc[i]['cen_lon'],Precippath,  meta.iloc[i]['cell_id'], year, dates)):
                i for i in tqdm(range(nsites))}
        
    print(f"Job complete for getting precipiation datdata, all precipitation data can be found in {Precippath}")