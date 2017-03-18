#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 13 22:17:01 2017

@author: Yefee
"""


import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import utils as utl


@xr.register_dataset_accessor('cam')
class CAMDiagnosis(object):
    def __init__(self, xarray_obj):
        self._obj = xarray_obj


    # precipation
    @property
    def precp(self):
        try:
            precc = self._obj.PRECC
            precl = self._obj.PRECL
            precp = (precc + precl) * 86400 * 1000 # convert to mm/day
            precp.name = 'precp'
        except:
            raise ValueError('object has no PRECC.')
        return precp

    # d18op
    @property
    def d18op(self):
        try:
            p16 = self._obj.PRECRC_H216Or + self._obj.PRECSC_H216Os + \
            self._obj.PRECRL_H216OR + self._obj.PRECSL_H216OS

            p18 = self._obj.PRECRC_H218Or + self._obj.PRECSC_H218Os + \
            self._obj.PRECRL_H218OR + self._obj.PRECSL_H218OS

            p16.values[p16.values < 1e-50] = np.nan
            d18op = (p18 / p16 -1)*1000
            d18op.name = 'd18op'
        except:
            raise ValueError('object has no PRECRC_H216Or.')
        return d18op

@xr.register_dataset_accessor('pop')
class POPDiagnosis(object):
    def __init__(self, xarray_obj):
        self._obj = xarray_obj


    # amoc
    @property
    def amoc(self):
        try:
            moc = self._obj.MOC[:, 1, 0, :, :]
            moc.values[np.abs(moc.values) < 1e-6] = np.nan
            # amoc area
            if moc.moc_z[-1] > 1e5:
                z_bound = moc.moc_z[(moc.moc_z > 2e4) & (moc.moc_z < 5e5)] #cm
            else:
                z_bound = moc.moc_z[(moc.moc_z > 2e2) & (moc.moc_z < 5e3)] #m
            lat_bound = moc.lat_aux_grid[
                        (moc.lat_aux_grid > 10) & (moc.lat_aux_grid < 60)]
            amoc = moc.sel(moc_z=z_bound).sel(lat_aux_grid=lat_bound).groupby('time').max()
        except:
            raise ValueError('object has no MOC.')
        return amoc

    # convert depth unit to m
    def chdep(self):
        if self._obj.z_t[-1] > 1e5:
            self._obj['z_t'] /= 1e2
        else:
            pass

    @property
    def ocnreg(self):
        return utl.region()

@xr.register_dataarray_accessor('utils')
class Utilities(object):
    def __init__(self, xarray_obj):
        self._obj = xarray_obj

    # regrid pop variables
    def regrid(self):
        import pyresample

        lon_curv = self._obj.TLONG.values
        lon_curv[lon_curv>180] = lon_curv[lon_curv>180] - 360
        lat_curv = self._obj.TLAT.values
        lon = np.arange(-180.,181,1)
        lat = np.arange(-90.,91,1)
        lon_lin, lat_lin = np.meshgrid(lon,lat)
        lon_lin = pyresample.utils.wrap_longitudes(lon_lin)
        #define the grid
        orig_def = pyresample.geometry.SwathDefinition(lons=lon_curv, lats=lat_curv)
        targ_def = pyresample.geometry.SwathDefinition(lons=lon_lin, lats=lat_lin)
        rgd_data = pyresample.kd_tree.resample_nearest(orig_def, self._obj.values.squeeze(),
        targ_def, radius_of_influence=1000000, fill_value=np.nan)

        return xr.DataArray(rgd_data, coords=[lat,lon], dims=['lat', 'lon'])

    def gbmean(self):

        lonmn = self._obj.mean('lon')
        lat_rad = xr.ufuncs.deg2rad(self._obj.lat)
        lat_cos = np.cos(lat_rad)

        return lonmn * lat_cos / lat_cos.sum()


    def gbmeanpop(self):
        if self._obj.size > 1e5:
            return self._obj / utl.tarea_g16.sum()

    def zonalmean(self):
        return self._obj.mean('lon')

    def selloc(self,loc='green_land', grid_method='natural'):

        if grid_method == 'natural':
            lat = self._obj.lat
            lon = self._obj.lon
        elif grid_method == 'T_grid':
            lat = self._obj.TLAT
            lon = self._obj.TLONG
        elif grid_method == 'U_grid':
            lat = self._obj.ULAT
            lon = self._obj.ULONG

#        if lon.max() > 180:
#            lon = lon[lon>180] - 180
        # later shall be wrapped into utils module
        loc = utl.locations[loc]
        return self._obj.where((lat > loc[0]) & (lat < loc[1]) & (lon > loc[2])
                               & (lon < loc[3]))
#        if loc == 'green_land':
#            return self._obj.where((lat > 72) & (lat < 73) & (lon > 321)
#                & (lon < 323))
#        elif loc == 'Brazil':
#            return self._obj.where((lat > -25) & (lat < -15) & (lon > 290)
#                & (lon < 310))
#        elif loc == 'Hulu':
#            return self._obj.where((lat > 30.5) & (lat < 33.5) & (lon > 117.5)
#                & (lon < 120.5))
#        else:
#            raise ValueError('Loc is unsupported.')

    def quickmap(self, ax=None, central_longitude=180, cmap='BlueDarkRed18'):

        import cartopy.crs as ccrs
        from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
        import nclcmaps

        if central_longitude == 180:
            xticks = [0, 60, 120, 180, 240, 300, 359.99]
        elif central_longitude == 0:
            xticks = [-180, -120, -60, 0, 60, 120, 180]
        else:
            central_longitude=180
            xticks = [0, 60, 120, 180, 240, 300, 359.99]
            print("didn't explicitly give center_lat, use 180 for defalut.")


        if ax is None:

            ax = plt.axes(projection=ccrs.PlateCarree(central_longitude=central_longitude))
#            ax = plt.axes(projection=ccrs.Orthographic(-80, 35))

        cmaps = nclcmaps.cmaps(cmap)
        self._obj.plot(ax=ax,cmap = cmaps,transform=ccrs.PlateCarree(),
                       cbar_kwargs={'orientation': 'horizontal',
                                    'fraction':0.09,
                                    'aspect':15})

        #set other properties
        ax.set_global()
        ax.coastlines(linewidth=0.6)
        ax.set_xticks(xticks, crs=ccrs.PlateCarree())
        ax.set_yticks([-90, -60, -30, 0, 30, 60, 90], crs=ccrs.PlateCarree())
        lon_formatter = LongitudeFormatter(zero_direction_label=True,
                                           number_format='.0f')
        lat_formatter = LatitudeFormatter()
        ax.xaxis.set_major_formatter(lon_formatter)
        ax.yaxis.set_major_formatter(lat_formatter)
        ax.set_xlabel('')
        ax.set_ylabel('')
        return ax

