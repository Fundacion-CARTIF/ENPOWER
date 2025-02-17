# -*- coding: utf-8 -*-
"""
Created on Thu Nov 10 10:28:46 2022

@author: albbel
"""

# import calmap
import calplot
from datetime import datetime
import gc
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os
import time

start_time = time.time()

#Create an empty dataframe to append new files and define path to pick files
df = pd.DataFrame()
fpath = 'd:\Desktop\calendar\plots\*.csv'
demo = 'Riga Imanta'
datelimit = False # True if there is a date from which data is valid
frstdt = '2022-03-03 00:00:00' # First valid date to be included in the plot

#### Parameters of the Calendar plots ####
showplots = False # If True, plots are displayed
dpiplots = 220    # dpi (resolution) of the plots
fntsz = 20        # Font size of the years
fntwght = 'normal'# Font weight of the years: normal, bold, italic...


#Import all daily weather files (*.csv) from the indicated folder
for filename in glob.glob(fpath):
   with open(os.path.join(os.getcwd(), filename), 'r') as f:
       #Read new *.csv files, setting 'date' to index.
       df_imp = pd.read_csv(f, sep=",", parse_dates=['timestamp'], 
                            dayfirst=True, index_col='timestamp')
       #Append new imported files, sorted by date.
       df = df.append(df_imp).sort_values('timestamp')     
       
if datelimit == True: df = df[df.index >= frstdt]
df = df.fillna(np.NaN)
    
# Para cada columna del df (cada variable), se crea una serie con el nombre
# de la variable y se "agrupa" por: hora, día, mes; suma y promedio.
# import sys
# sys.exit(0)
for i in df.columns.values:
    locals()[i] = df[i]
    var = locals()[i]
    nm = var.name
    # Se eliminan los valores de temperaturas menores de -35 o mayores de 300
    if 'temp' in nm or 'Temp' in nm:
        df.loc[df[nm] > 300, nm] = np.NaN
        df.loc[df[nm] < -35, nm] = np.NaN    
    # Se eliminan los valores de viento mayores de 20 m/s (porque hay errores)
    if 'wind' in nm or 'Wind' in nm:
        df.loc[df[nm] > 20, nm] = np.NaN
    if any(item in nm for item in ['emp', 'HDh', 'Wind', 'wind']):
        pass
    else:
        var = var*1000
    var = var.dropna()
    var.hourly_acc= var.groupby(pd.Grouper(freq='H')).sum()
    var.hourly= var.groupby(pd.Grouper(freq='H')).mean()
    var.daily_acc= var.groupby(pd.Grouper(freq='D')).sum()
    # 24h * 4 para tener el total de periodos 15 minutales en un día
    var.daily_count= var.groupby(pd.Grouper(freq='D')).count().div(24*4)
    var.daily= var.groupby(pd.Grouper(freq='D')).mean()
    var.monthly_acc= var.groupby(pd.Grouper(freq='M')).sum()
    var.monthly= var.groupby(pd.Grouper(freq='M')).mean() 

#############################################################################
#############################                ################################
############################# CALENDAR PLOTS ################################
#############################                ################################
############################################################################# 
    
    pl_DQ = calplot.calplot(var.daily_count, yearlabel_kws={
                'fontsize': fntsz, 'fontweight': fntwght},
                fillcolor='#FCFCFC', cmap='RdYlGn', colorbar=True, 
                suptitle = "Data quality of: " + nm + 
                " - " + demo + " (0 - No data / 1 - No gaps)",
                tight_layout=False)
    if any(item in nm for item in ['emp', 'umid', 'RH', 'flow', '_T',
                                   'Wind', 'wind', 'tatus', 'CO2']):
        pass
    else:
        pl_Acc = calplot.calplot(var.daily_acc, yearlabel_kws={
                'fontsize': fntsz, 'fontweight': fntwght},
                fillcolor='#FCFCFC', cmap='PuRd', colorbar=True, 
                suptitle = "Daily accumulated values - " + nm + 
                " - " + demo, tight_layout=False)
        pl_Acc[0].savefig(nm + '_SummedValues.png', dpi = dpiplots, 
                bbox_inches='tight')
        if showplots == False: plt.close(pl_Acc[0])
    pl_Mean = calplot.calplot(var.daily, yearlabel_kws={
                'fontsize': fntsz, 'fontweight': fntwght},
                fillcolor='#FCFCFC', cmap='Reds', colorbar=True, 
                suptitle = "Daily average values - " + nm + 
                " - " + demo, tight_layout=False)
    ############################ Save plots ################################
    pl_DQ[0].savefig(nm + '_DataQuality.png', dpi = dpiplots, 
                     bbox_inches='tight')
    pl_Mean[0].savefig(nm + '_MeanValues.png', dpi = dpiplots,  
                       bbox_inches='tight')
    ############################ Close plots ################################
    if showplots == False:
        plt.close(pl_DQ[0])
        plt.close(pl_Mean[0])
    plt.clf()
    gc.collect()

print("--- %s seconds ---" % round((time.time() - start_time),5))