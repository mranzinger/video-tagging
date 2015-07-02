
import StringIO
import math
import platform
import sys
import itertools
import requests, urllib, urllib2
import json
from moviepy.editor import *
from multiprocessing import Pool, Lock, Queue, Manager

if 'Darwin' == platform.system():
    from PIL import Image
else:
    import Image



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
    textURL = "http://access.alchemyapi.com/calls/image/ImageGetRankedImageSceneText?apikey=%s&outputMode=json&imagePostMode=raw" % a_apiKey

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
        #if i >= 32:
        #    break
        
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
    l_pool = Pool(processes = 8)
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


    #l_timedKeywords = []
    #print "Collecting results"
    #while not l_resultQueue.empty():
    #    l_timedKeywords.append(l_resultQueue.get())

    ##sort by timestamp
    #l_rawTimeSeries = sorted(l_timedKeywords, key = lambda x: x[0])
    #l_timeSeries = { "results" : []}

    ##display results of frame tagging
    #for k, g in itertools.groupby(l_rawTimeSeries, lambda x: x[0]):
    #    l_resultsDict = {}
    #    l_element = { "timestamp" : k}
    #    for x in g:
    #        for tag, score in x[1].iteritems():
    #            if tag not in l_resultsDict:
    #                l_resultsDict[tag] = 0
    #            l_resultsDict[tag] = l_resultsDict[tag] + score / float(l_imagesPerSecond)
    #    l_keywordList = []
    #    for tag in l_resultsDict:
    #        l_keywordList.append({ 'text' : tag, 'score' : l_resultsDict[tag] })
    #    l_element["keywords"] = l_keywordList
    #    l_timeSeries['results'].append(l_element)
    #    
    #print l_timeSeries
    #return l_timeSeries

# def GetCelebrityTimeSeries(a_timeSeries):
#     cts = {}
#     for (time, dictionary) in a_timeSeries:
#         cts[time] = []
#         for face in dictionary['face']:
#             if 'identity' not in face.keys():
#                 continue
#             cts[time].append((face['identity']['name'], float(face['identity']['score'])))
#     # print "printing stats..."
#     # print stats
#     return cts

# returns a list of times as a function of person
def GetCelebrityTimeSeries(a_timeSeries):
    cts = {}
    for (time, dictionary) in a_timeSeries:
        for face in dictionary['face']:
            if 'identity' not in face.keys():
                continue
            if face['identity']['name'] not in cts.keys():
                cts[face['identity']['name']]=[] 
            cts[face['identity']['name']].append(float(time))
    print cts
    return cts

def CollectStats(a_timeSeries):    
    stats = { }
    stats["celebrity_time_series"] = GetCelebrityTimeSeries(a_timeSeries)
    stats['common_tags'] = GetCommonTagStats(a_timeSeries)
    stats['actor_presence'] = GetActorPresenceStats(a_timeSeries)

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

def GetActorPresenceStats(a_timeSeries):

    genderStats = { }
    ageStats = { }
    actorStats = { }
    
    for ts, evt in a_timeSeries:

        for face in evt['face']:

            if u'gender' in face:

                gender = face[u'gender'][u'gender']
                score = float(face[u'gender'][u'score'])

                if not gender in genderStats:
                    genderStats[gender] = 0.0
                genderStats[gender] += score

            if u'age' in face:

                rg = face[u'age'][u'ageRange']
                score = float(face[u'age'][u'score'])

                if not rg in ageStats:
                    ageStats[rg] = 0.0
                ageStats[rg] += score

            if u'identity' in face:

                name = face[u'identity'][u'name']
                score = float(face[u'identity'][u'score'])

                if not name in actorStats:
                    actorStats[name] = 0.0
                actorStats[name] += score

    def NormStats(a_stats):
        acc = 0.0
        for k, v in a_stats.iteritems():
            acc += v
        for k in a_stats:
            a_stats[k] /= acc

    NormStats(genderStats)
    NormStats(ageStats)
    #NormStats(actorStats)
    for k in actorStats:
        actorStats[k] /= len(a_timeSeries)

    return {
        'gender': genderStats,
        'age': ageStats,
        'actorStats': actorStats
    }

def WriteJson(a_obj, a_filename):
    f = open(a_filename, 'w')

    f.write(json.dumps(a_obj, sort_keys=True, indent=4, separators=(',', ': ')))

    f.close()

def Main():

    if len(sys.argv) > 2:
        l_filename = sys.argv[1]
        l_apiKey = sys.argv[2]
    else:
        print "Filepath of source video required\nExample: $ python videoTag.py /home/Ilovecats.mp4"
        return
    
    l_timeSeries = GetTimeSeriesForVideo(l_filename, l_apiKey)

    WriteJson(l_timeSeries, 'time_series.json')

    stats = CollectStats(l_timeSeries)

    WriteJson(stats, 'movie_stats.json')

    print 'All Done!!!'

    return


if __name__ == "__main__":
    Main()
