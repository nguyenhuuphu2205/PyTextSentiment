# -*- coding: utf-8 -*-

import sys
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')

import os
import numpy
import re
import time
import datetime

# source: https://github.com/geduldig/TwitterAPI
from TwitterAPI import TwitterAPI, TwitterOAuth, TwitterRequestError, TwitterConnectionError

# for clean console output, let's suppress them for now.
import warnings
warnings.filterwarnings("ignore")

# custom modules
import Utility
import GeoLocationModule
import TranslationModule
import EmotionTagger
import UnSupervised
import Supervised


# Data Retrieval Class for Twitter ####################################################################################
class DataRetrieval_Twitter:
    def __init__(self):
        self.aBasePath = os.getcwd()
        self.globalCSVDataStorePath = self.aBasePath + "/assets/twitterData/myJsonOutput.csv"

        # API Object: Never call directly
        """
        Source: https://docs.python.org/2/tutorial/classes.html#tut-private
        “Private” instance variables that cannot be accessed except from inside an object don’t exist in Python.
        """
        self.globalAppObj = None
        self.globalEmoObj = None


    def getAppObject(self):
        if self.globalAppObj is None:
            # Using OAuth1...
            o = TwitterOAuth.read_file()
            self.globalAppObj = TwitterAPI(o.consumer_key, o.consumer_secret, o.access_token_key, o.access_token_secret)

        return self.globalAppObj



    def getEmoTaggerObject(self):
        if self.globalEmoObj is None:
            # Using OAuth1...
            self.globalEmoObj = EmotionTagger.SyntacticTagger()

        return self.globalEmoObj


    def getFeedsByText(self, api=None, f1=None, isLive=True, annotation=None,
                       queryText=u'a', textLang=None, isTrain=False, locationArea=None):

        if api is None:
            api = self.getAppObject()

        iteratorRunCount = 0
        isDuplicateList = []
        tweetsRecorded = 0
        reTryCount = 0
        MAX_TWEET = 20
        MAX_TRIES = 10
        queryParam = {}
        while True:
            try:

                # TODO: think of better ways to handle this
                if (iteratorRunCount >= 10): # hack, this limits the number of tweets you want to retrieve
                    print( "\n ASSUMPTION: there are no tweets as of now. Let's go back! \n\n")
                    print(u"\n\n\n")
                    return
                else:
                    # try some iteration with original search
                    pass

                # Let's take 60 seconds pause before each API call;
                # 2017 twitter rate limit is 15 API calls per 15 mins in total per account;
                time.sleep(60)

                if (textLang is not None):
                    queryText = queryText + ' lang:' + textLang

                queryParam['rpp'] = 100
                if ((isLive==True) or (queryText is None)):
                    if queryText is not None:
                        queryParam['track'] = queryText
                    if (locationArea is None) and (queryText is not None):
                        # live tweets without location filter
                        iterator = api.request('statuses/filter', queryParam).get_iterator()
                    elif (locationArea is not None)and (queryText is not None):
                        # live tweets with location filter
                        queryParam['locations']=GeoLocationModule.getGeoArea(area=locationArea)
                        iterator = api.request('statuses/filter', queryParam).get_iterator()
                    elif (locationArea is not None)and (queryText is None):
                        self.liveFeedsByLocation(api=api, locationArea=locationArea)
                    else:
                        print("ERROR: locationArea and queryText cannot be None together")
                        exit(-1)

                else: # isLive==False
                    queryParam['q'] = queryText
                    if locationArea is None:
                        # search tweets without location filter
                        iterator = api.request('search/tweets', queryParam).get_iterator()
                    else:
                        # search tweets with location filter
                        queryParam['locations']=GeoLocationModule.getGeoArea(area=locationArea)
                        iterator = api.request('search/tweets', queryParam).get_iterator()

                iteratorRunCount += 1

                for item in iterator:
                    if ( ('text' in item) and (item[u'id'] not in isDuplicateList) and (item[u'retweeted']==False) ):

                        rawTextClean1 = item[u'text'].encode('utf-8')
                        rawTextClean2 = rawTextClean1.strip()
                        rawTextClean3 = rawTextClean2.replace("#"," ")  # remove hashtags
                        rawTextClean4 = re.sub(r'https?:\/\/.*[\r\n]*', '', rawTextClean3, flags=re.MULTILINE) # remove urls

                        if (25 < len(rawTextClean4))   and   (len(item[u'text']) < 140): # take tweets with sufficient text
                            isDuplicateList.append(item[u'id'])
                            tweetsRecorded += 1

                            rawEnText = TranslationModule.getEnglish(rawTextClean4)
                            fineEnText = rawEnText.replace(",", " ").replace(";", " ")
                            print( str(tweetsRecorded) + ":\t" + item[u'lang'] + ",\t\t" + annotation.lower() + "\t\t:" + queryText + "\t\t:" + str(len(fineEnText)))
                            print( fineEnText )

                            emoVector = self.getEmoTaggerObject().consolodateResult(fineEnText)
                            listRes = []
                            keyRes  = sorted(emoVector)
                            for key in keyRes:
                                listRes.append(emoVector[key])
                            print(listRes, keyRes)

                            listStr1 = str(listRes).replace(",", " ")
                            listStr2 = listStr1[1:-1]
                            listStr3 = listStr2.split()
                            listVector = [float(i) for i in listStr3 if Utility.RepresentsNum(i)]

                            emoLabel = annotation
                            if len(listVector) != 0:
                                assert (len(listVector) == 8) # emo-vector length should be 8;
                                if True: # Training Only
                                    emoTypesCount = 0
                                    for i in range(0,8,1):
                                        if (listVector[i] > 0.0):
                                            emoTypesCount += 1

                                    if (emoTypesCount == 0):
                                        emoLabel = "neutral"
                                        print(">> No Emotion \n\n\n")
                                        continue
                                    elif (emoTypesCount >= 5):
                                        emoLabel = "mixed"
                                        print(">> Mixed Emotion \n\n\n")
                                        continue
                                    else:
                                        emoLabel = annotation

                            if isTrain == True:
                                f1.write( unicode(item[u'id_str']) + "," + unicode(item[u'created_at']) + "," + unicode(item[u'lang']) + "," + unicode(emoLabel).lower() + "," + unicode(fineEnText).replace("\n", " ").replace("\r", " ") + "," + "\n" )
                                f1.flush()
                                os.fsync(f1.fileno())
                            else:
                                Supervised.getPrediction(npVector = numpy.array([ listRes ]), model='NBC')
                                Supervised.getPrediction(npVector = numpy.array([ listRes ]), model='SVC')

                            if (tweetsRecorded >= MAX_TWEET) or (reTryCount >= MAX_TRIES):
                                print( "\n ReTry Count: " + str(reTryCount) + "\n\n")
                                print(u"\n\n\n")
                                return

                            print(u"\n\n\n")

                    elif 'disconnect' in item:
                        event = item['disconnect']
                        reTryCount += 1

                        if event['code'] in [2,5,6,7]:
                            # something may or may NOT need to be fixed before re-connecting
                            raise Exception(event['reason'])
                        else:
                            # temporary interruption, re-try request
                            break

                    elif (iteratorRunCount > 0) and (tweetsRecorded < MAX_TWEET): # Condition when no more unique tweets are found, go back
                        # TODO: think of better ways to handle this
                        if (queryText[0] == '#'):
                            return # temporary return
                            queryText = queryText[1:]
                            break
                        else:
                            print( "\n No more tweets as of now \n\n")
                            print(u"\n\n\n")
                            return

                    else:
                        pass

            except TwitterRequestError as e:
                if e.status_code < 500:
                    print "\n\n" + "MJAGLAN EXCEPTION:\n" + str(e) + "\n\n"
                else:
                    # temporary interruption, re-try request
                    pass

            except TwitterConnectionError:
                # temporary interruption, re-try request
                pass


    # Method intended to find most popular tends on twitter in a city
    def liveFeedsByLocation(self, api=None, locationArea="New York City, NY", filePath=None):
        if api is None:
            api = self.getAppObject()

        if filePath == self.globalCSVDataStorePath:
            print("WARNING: Attempt to write on Train Data File!")
            exit(-1)
        else:
            f2 = open(filePath, 'a+')

        langCount = {}
        langEmo = {}
        queryParam = {}
        queryParam['locations'] = GeoLocationModule.getGeoArea(area=locationArea)
        queryParam['rpp'] = 100
        recordCount = 0
        while True:
            try:
                # Let's take 60 seconds pause before next API call;
                # 2017 twitter rate limit is 15 API calls per 15 mins in total per account;
                time.sleep(60)

                iterator = api.request('statuses/filter', queryParam).get_iterator()
                for item in iterator:
                    if 'text' in item:
                        if item[u'lang'] in langCount.keys():
                            langCount[item[u'lang']] += 1
                        else:
                            langCount[item[u'lang']] = 1

                        rawTextClean1 = item[u'text'].encode('utf-8')
                        rawTextClean2 = rawTextClean1.strip()
                        rawTextClean3 = rawTextClean2.replace("#"," ")  # remove hashtags
                        rawTextClean4 = re.sub(r'https?:\/\/.*[\r\n]*', '', rawTextClean3, flags=re.MULTILINE) # remove urls
                        rawEnText = TranslationModule.getEnglish(rawTextClean4)
                        fineEnText = rawEnText.replace(",", " ").replace(";", " ")
                        emoVector = self.getEmoTaggerObject().consolodateResult(fineEnText)
                        listRes = []
                        keyRes  = sorted(emoVector)
                        for key in keyRes:
                            listRes.append(emoVector[key])

                        ##### CONSOLE #
                        print '{}: {}'.format(item[u'lang'], rawTextClean2)
                        print (zip(keyRes, listRes))
                        print '\n\n\n'

                        listStr1 = str(listRes).replace(",", " ")
                        listStr2 = listStr1[1:-1]
                        listStr3 = listStr2.split()
                        listVector = [float(i) for i in listStr3 if Utility.RepresentsNum(i)]
                        if len(listVector) == 0:
                            listVector = [0.0] * len(langEmo[langEmo.keys()[0]])
                        if item[u'lang'] in langEmo.keys():
                                langEmo[item[u'lang']] = [sum(x) for x in zip(langEmo[item[u'lang']], listVector)]
                        else:
                            langEmo[item[u'lang']] = listVector

                        assert len(langCount.keys()) == len(langEmo.keys()) ################################## ASSERT #
                        recordCount += 1

                        # if recordCount > 500:
                        #     print("record count: " + str(recordCount))
                        #     recordCount = 0
                        #     f2.write( u'LOCATION' + "," + u"LANGUAGE" + "," + u"LANGUAGE_COUNT" + "," + u'EMO VECTOR' + "," +  "\n")
                        #     for aKey in langCount:
                        #         f2.write( unicode(locationArea) + "," + unicode(aKey) + "," + unicode(langCount[aKey]) + "," + unicode(langEmo[aKey]) + "," +  "\n")
                        #     f2.write( "\n\n\n")
                        #     f2.flush()
                        #     os.fsync(f2.fileno())

                    elif 'disconnect' in item:
                        event = item['disconnect']
                        if event['code'] in [2,5,6,7]:
                            # something needs to be fixed before re-connecting
                            raise Exception(event['reason'])
                        else:
                            # temporary interruption, re-try request
                            break

            except TwitterRequestError as e:
                print("record count: " + str(recordCount))
                f2.write( u'LOCATION' + "," + u"LANGUAGE" + "," + u"LANGUAGE_COUNT" + "," + u'EMO VECTOR' + "," +  "\n")
                for aKey in langCount:
                    f2.write( unicode(locationArea) + "," + unicode(aKey) + "," + unicode(langCount[aKey]) + "," + unicode(langEmo[aKey]) + "," +  "\n")
                f2.write( "\n\n\n")
                f2.flush()
                os.fsync(f2.fileno())

                if e.status_code < 500:
                    # something needs to be fixed before re-connecting
                    print "\n\nSomething needs to be fixed before re-connecting:\n"+str(e)+"\n\n"
                    pass
                else:
                    # temporary interruption, re-try request
                    pass

            except TwitterConnectionError:
                # print("record count: " + str(recordCount))
                f2.write( u'LOCATION' + "," + u"LANGUAGE" + "," + u"LANGUAGE_COUNT" + "," + u'EMO VECTOR' + "," +  "\n")
                for aKey in langCount:
                    f2.write( unicode(locationArea) + "," + unicode(aKey) + "," + unicode(langCount[aKey]) + "," + unicode(langEmo[aKey]) + "," +  "\n")
                f2.write( "\n\n\n")
                f2.flush()
                os.fsync(f2.fileno())

                # temporary interruption, re-try request
                pass




    def getFeeds(self, fullFilePath=None):

        apiObj = self.getAppObject()
        if fullFilePath is None:
            print("ERROR: File Name for Data Storage is missing!")
            exit(-1)

        if not os.path.isfile(fullFilePath):
            f2 = open(fullFilePath, 'a+')
            f2.write( u'TWEET' + "," + u"TWEET TIMESTAMP" + "," + u'ORIGINAL LOCALE' + "," + u"ANNOTATION" + "," + u"RAW EN TEXT" + "," + u"EMO VECTOR"+"\n")
        else:
            f2 = open(fullFilePath, 'a')

        # QUERY CONSTRAINTS #
        regionName  = None # Ex: "Seoul, South Korea"
        localeCode  = None # Ex: "ko"
        setTrainMode = False
        setLive = False
        isHashTag = True

        if setTrainMode == False:
            resPath = self.aBasePath + '/assets/Resource/searchKeys/testFiles'
        else:
            resPath = self.aBasePath + '/assets/Resource/searchKeys'

        from os import listdir
        from os.path import isfile, join
        onlyfiles = sorted([f for f in listdir(resPath) if (isfile(join(resPath, f)) and not f.endswith("~"))])
        for aFile in onlyfiles:

            myAnnotation, extension = os.path.splitext(aFile.lower())
            with open(join(resPath,aFile), 'r') as f1:
                read_data = f1.readlines()

                wordCount = 0
                for eachWord in read_data:
                    wordCount += 1
                    if wordCount > 2000: # only 2000 words
                        break

                    aWord = str(eachWord).strip('\r\n').lower()

                    if isHashTag == True:
                        aWord = "".join(aWord.split())
                        aWord = "#" + aWord # prepend hashtag for better relevance

                    if len(aWord) > 2: # avoid mess
                        self.getFeedsByText(api=apiObj, f1=f2, isLive=setLive, annotation=myAnnotation, queryText=unicode(aWord), textLang=localeCode, isTrain=setTrainMode, locationArea=regionName)
                    else:
                        print("\n[NOTE]: Bad query text!")

                f1.close()
        f2.close()

        if setTrainMode == True:
            UnSupervised.getCluster(noOfTimesToRunKMeans=29)


def main():
    obj = DataRetrieval_Twitter()

    print "ARGS LIST:"
    inputFilePath = obj.aBasePath + "/assets/input.txt"
    inputList = [line.rstrip('\n') for line in open(inputFilePath)]
    for eachInput in inputList:
        print eachInput

    try:
        newFilePath = obj.aBasePath + "/assets/twitterData/" + unicode(inputList[0])
    except:
        newFilePath = obj.globalCSVDataStorePath
        print("Default File: " + newFilePath)

    try:
        location = unicode(inputList[1])
    except:
        location = "Seoul, South Korea"
        print("Default Location: " + location)

    try:
        methodName = unicode(inputList[2]).lower()
    except:
        methodName = "location"
        print("Default Method: " + methodName)


    ts = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    if methodName == "location":
        # python TwitterStream.py "Seoul.SouthKorea.csv" "Seoul, South Korea" "location"
        newFilePath = newFilePath[:-4] + "-" + location + newFilePath[-4:]
        newFilePath = newFilePath[:-4] + "-" + ts       + newFilePath[-4:]
        print "Parameters: \n %s \n %s \n %s" % ("liveFeedsByLocation", location, newFilePath)
        obj.liveFeedsByLocation(api=obj.getAppObject(), locationArea=location, filePath=newFilePath)
    else:
        # python TwitterStream.py "Train.File.Name.csv" "any thing" "any thing"
        newFilePath = newFilePath[:-4] + ts + newFilePath[-4:]
        print "Parameters: \n %s \n %s" % ("getFeeds", newFilePath)
        obj.getFeeds(newFilePath)


if __name__ == '__main__':
    main()
