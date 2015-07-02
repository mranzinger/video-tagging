
import StringIO
import math
import Image
import sys
import itertools
import requests, urllib, urllib2
import json
from moviepy.editor import *
from multiprocessing import Pool, Lock, Queue, Manager


def GetCallJson(a_url, a_jpeg):
    try:
        print 'Calling API:', a_url
        results = requests.post(url= a_url, data= a_jpeg)
        js = results.json()

        return js

    except:
        print "Trouble with AlchemyAPI:", a_url
        return None

def AlchemyGetImageTag(a_jpeg, a_time, a_queue, a_apiKey):
    # Some set up

    tagURL = "http://access.alchemyapi.com/calls/image/ImageGetRankedImageKeywords?apikey=%s&outputMode=json&imagePostMode=raw&forceShowAll=1" % a_apiKey
    faceURL = "http://access.alchemyapi.com/calls/image/ImageGetRankedImageFaceTags?apikey=%s&outputMode=json&imagePostMode=raw" % a_apiKey
    #textURL = "http://access.alchemyapi.com/calls/image/ImageGetRankedImageSceneText?apikey=%s&outputMode=json&imagePostMode=raw" % a_apiKey

    jsTags = GetCallJson(tagURL, a_jpeg)
    jsFace = None
    jsText = None
    
    jsFace = GetCallJson(faceURL, a_jpeg)
    #jsText = GetCallJson(textURL, a_jpeg)

    comb = { }
    if jsTags != None:
        comb['tags'] = jsTags['imageKeywords']
    else:
        comb['tags'] = []

    if jsFace != None:    
        comb['face'] = jsFace['imageFaces']
    else:
        comb['face'] = []

    if jsText != None:
        comb['text'] = jsText['sceneText']
    else:
        comb['text'] = ''

    element = (math.floor(a_time), comb)
    a_queue.put(element)

    #print comb


   # try:
   #     l_results = requests.post(url = l_baseURL, data = a_jpeg)
   #     l_json = l_results.json()
   #     l_dict = {}

   #     for l_kwResult in l_json["imageKeywords"]:           
   #         l_dict[l_kwResult['text']] = float(l_kwResult["score"])

   #     l_element = ( math.floor(a_time), l_dict )
   #     a_queue.put(l_element)
   # except:
   #     print "Trouble with AlchemyAPI"
   #     l_element = ( math.floor(a_time) , {} )
   #     a_queue.put(l_element)
   # return

def GetTimeSeriesForVideo(a_filename, a_apiKey):

    l_video = VideoFileClip(a_filename)
    l_videoLength = int(math.floor(l_video.duration))

    #set frequency of image capture from video
    l_imagesPerSecond = 2
    l_timeStep = float(1 / float(l_imagesPerSecond))

    l_images = []
    l_imagenames = []
    l_imagetimes = []
    
    for i in xrange(l_videoLength):
        print "Iteration %d" % i

        # Our goal: list of keywords for this iteration
        l_keywordList = {}
        l_timeStamps = [i + j * l_timeStep for j in xrange(l_imagesPerSecond)]
    
        # Extract frames, convert to images
        l_frames = [l_video.get_frame(j) for j in l_timeStamps]
        l_images += [Image.fromarray(j, "RGB") for j in l_frames]
        l_imagetimes += l_timeStamps
        l_imagenames += [ "frame_%.1f.jpg" % t for t in l_timeStamps ]
        # end of loop
    
    # Prepare to call AlchemyAPI
    l_pool = Pool(processes = 32)
    l_mgr  = Manager()
    l_resultQueue = l_mgr.Queue()
    print "Sending images to AlchemyAPI"
    for l_image in enumerate(l_images):
        
        l_buffer = StringIO.StringIO()
        l_image[1].save(l_buffer, format= 'JPEG')
        l_jpeg = l_buffer.getvalue()
        
        #async call to AlchemyAPI
        l_pool.apply_async(AlchemyGetImageTag, (l_jpeg, l_imagetimes[l_image[0]], l_resultQueue, a_apiKey))    
        #AlchemyGetImageTag(l_jpeg, l_imagetimes[l_image[0]], l_resultQueue, a_apiKey)
    
    l_pool.close()
    l_pool.join()

    l_timedResps = []
    while not l_resultQueue.empty():
        l_timedResps.append(l_resultQueue.get())

    # sort by timestamp
    return sorted(l_timedResps, key = lambda x: x[0])
    
def CollectStats(a_timeSeries):

    stats = { }

    stats['common-tags'] = GetCommonTagStats(a_timeSeries)

    return stats

def GetCommonTagStats(a_timeSeries):

    counts = { }

    for ts, evt in a_timeSeries:
        
        for tag in evt['tags']:
            
            txt = tag['text']
            conf = tag['score']

            if not txt in counts:
                counts[txt] = 0.0

            counts[txt] += float(conf)

    stats = []
    for k, v in counts.iteritems():

        pct = v / len(a_timeSeries)

        stats.append((pct, k))

    return sorted(stats, key=lambda x: x[0], reverse=True)[:5]

    #print a_timeSeries
    #f = open('time-series.json', 'w')
    #f.write(json.dumps(a_timeSeries, sort_keys=True, indent=4, separators=(',', ': ')))
    #f.close()

def Main():

    if len(sys.argv) > 2:
        l_filename = sys.argv[1]
        l_apiKey = sys.argv[2]
    else:
        print "Filepath of source video required\nExample: $ python videoTag.py /home/Ilovecats.mp4"
        return
    
    l_timeSeries = GetTimeSeriesForVideo(l_filename, l_apiKey)

    stats = CollectStats(l_timeSeries)

    f = open('movie_stats.json', 'w')

    f.write(json.dumps(stats, sort_keys=True, indent=4, separators=(',', ': ')))

    f.close()

    print 'All Done!!!'

    return


if __name__ == "__main__":
    Main()
