from urllib2 import urlopen
from lxml.html import parse
from lxml import etree
import datetime
import xml.etree.ElementTree as ET
import shapefile

# dependencies lxml, pykml

def create_prj_wgs84 (shp_path):
    # shp_path: '/home/silent/temp/4_days.shp'
    # create the PRJ file
    prj = open("%s.prj" % ('.').join(shp_path.split('.')[:-1]), "w")
    epsg = 'GEOGCS["WGS 84",'
    epsg += 'DATUM["WGS_1984",'
    epsg += 'SPHEROID["WGS 84",6378137,298.257223563]]'
    epsg += ',PRIMEM["Greenwich",0],'
    epsg += 'UNIT["degree",0.0174532925199433]]'
    prj.write(epsg)
    prj.close()




def get_dates_from_link (link):
    try:
        date_part = link[-17:]
        start_year = int(date_part[4:8])
        start_month = int(date_part[2:4])
        start_day = int(date_part[0:2])
        start_date = datetime.date(start_year,start_month,start_day)

        end_year = int(date_part[13:17])
        end_month = int(date_part[11:13])
        end_day = int(date_part[9:11])
        end_date = datetime.date(end_year, end_month, end_day)
    except:
        return 0, 0

    return start_date, end_date


def get_available_kmls ():
    url_base = 'https://sentinel.esa.int'

    page = urlopen(url_base + '/web/sentinel/missions/sentinel-1/observation-scenario/acquisition-segments')
    page_html = parse (page)

    hrefs = page_html.xpath('//a/@href')

    available_kmls = []

    for link in hrefs:
        if link.find('/documents/') > -1:
            start_date, end_date = get_dates_from_link(link)
            if start_date and end_date:
                current_segment = {'start_date': start_date, 'end_date': end_date, 'link': url_base + link}
                available_kmls.append(current_segment)

    return available_kmls


def get_sentinel_extents_dict (kml=None, kml_url=None):
    if kml:
        tree = ET.parse(kml)
    elif kml_url:
        remote_kml = urlopen(kml_url)
        tree = ET.parse(remote_kml)
    else:
        return 0

    root = tree.getroot()
    namespace = '{http://www.opengis.net/kml/2.2}'

    sentinelExtents = []

    for Document in root:
        for Folder in Document:
            if Folder.tag == (namespace + 'Folder'):
                for FolderSecondary in Folder:
                    if FolderSecondary.tag == (namespace + 'Folder'):
                        for Placemark in FolderSecondary:
                            if Placemark.tag == (namespace + 'Placemark'):

                                sentinelExtent = {'coordinates': 0, 'mode': 0, 'startTime': 0, 'endTime': 0, 'satId': 0, 'polarisation': 0}

                                for LinearRing in Placemark:
                                    # Extended data
                                    if LinearRing.tag == (namespace + 'ExtendedData'):
                                        for Data in LinearRing:
                                            for child in Data:
                                                if Data.attrib['name'] == 'Mode':
                                                    sentinelExtent['mode'] = child.text
                                                if Data.attrib['name'] == 'ObservationTimeStart':
                                                    sentinelExtent['startTime'] = child.text
                                                if Data.attrib['name'] == 'ObservationTimeStop':
                                                    sentinelExtent['endTime'] = child.text
                                                if Data.attrib['name'] == 'SatelliteId':
                                                    sentinelExtent['satId'] = child.text
                                                if Data.attrib['name'] == 'Polarisation':
                                                    sentinelExtent['polarisation'] = child.text

                                    # Coordinates
                                    if LinearRing.tag == (namespace + 'LinearRing'):
                                        for child in LinearRing:
                                            if child.tag == (namespace + 'coordinates'):
                                                sentinelExtent['coordinates'] = (child.text).replace('0 ','')

                                sentinelExtents.append(sentinelExtent)
    return sentinelExtents

def chunks(l, n):
    n = max(1, n)
    return [l[i:i + n] for i in range(0, len(l), n)]

def delete_elements_with_given_dimension(l, dim):
    new_l = []
    for element in l:
        if not len(element) == dim:
            new_l.append(element)
    return new_l

def prepare_coordinates (coords):
    coords_list = delete_elements_with_given_dimension(chunks(coords.split(','),2),1)
    new_coords_list = []
    for coords in coords_list:
        new_coords_list.append([float(coords[0]),float(coords[1])])
    return new_coords_list

def get_date_str_from_sentinel_extent (sentinelDateStr):
    year = int(sentinelDateStr[0:4])
    month = int(sentinelDateStr[5:7])
    day = int(sentinelDateStr[8:10])
    return datetime.date(day=day,month=month,year=year)

def create_shapefile_with_extents (sentinelExtents, path, dates = None):

    w = shapefile.Writer(shapefile.POLYGON)
    w.field('ID','C',40)
    w.field('SAT','C',40)
    w.field('MODE','C',40)
    w.field('POLARIZ','C',40)
    w.field('START','C',40)
    w.field('END','C',40)

    i = 0
    for sentinelExtent in sentinelExtents:
        if dates:
            if not get_date_str_from_sentinel_extent(sentinelExtent['startTime']) in dates:
                continue
        w.poly(parts=[prepare_coordinates(sentinelExtent['coordinates'])])
        w.record(str(i),sentinelExtent['satId'],sentinelExtent['mode'],sentinelExtent['polarisation'],sentinelExtent['startTime'],sentinelExtent['endTime'])
        i += 1
    #print 'saving...'
    w.save(path)
    create_prj_wgs84(path)



def get_sentinel_extents_and_create_shapefile_for_dates (path, dates):
    available_kmls = get_available_kmls()
    for kml in available_kmls:
        start_date = kml['start_date']
        end_date = kml['end_date']
        date_is_between = True
        for date in dates:
            if not (start_date <= date <= end_date):
                date_is_between = False

        if date_is_between:
            sentinelExtents = get_sentinel_extents_dict(kml_url=kml['link'])
            create_shapefile_with_extents(sentinelExtents,path,dates)
            return 1
    return 0

def get_sentinel_extents_for_today_n_days (n, path):
    n_days = []
    for i in range(n):
        n_days.append(datetime.date.today()+datetime.timedelta(days=i))

    if not get_sentinel_extents_and_create_shapefile_for_dates(path,n_days):
        print 'Dates not available'




get_sentinel_extents_for_today_n_days(5,'/home/silent/temp/5_days.shp')
