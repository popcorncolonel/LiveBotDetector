import requests
import json
import sys # for printing to stderr and restarting program
import os

restart_on_failure = False 
MAX = 100
limit = str(MAX)
offset = str(0)

def removeNonAscii(s): return "".join([x if ord(x) < 128 else '?' for x in s])

"""
r = requests.get('https://api.twitch.tv/kraken/games/top' +
                 '?limit=' + limit)
flag = 1
while flag: #jank bugfix - sometimes can't read json
    try:
        gamedata = r.json()
        flag = 0
    except:
        pass
"""
def restart_program():
    python = sys.executable
    os.execl(python, python, * sys.argv)

#user_total_views: 
#   returns the number of total views twitch.tv/user has had.
#user is a string representing http://www.twitch.tv/<user>
def user_total_views(user):
    try:
        r = requests.get("https://api.twitch.tv/kraken/search/channels?q=" + user)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        return user_total_views(user)
    while(r.status_code != 200):
        try:
            r = requests.get("https://api.twitch.tv/kraken/search/channels?q=" + user)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            return user_total_views(user)
    chan = r.json()
    if (chan['channels'][0]['name'] == user):
        return chan['channels'][0]['views']

#user_viewers: 
#   returns the number of viewers twitch.tv/user currently has. returns 0 if offline.
#user is a string representing http://www.twitch.tv/<user>
def user_viewers(user):
    global restart_on_failure
    req = 0
    try:
        req = requests.get("https://api.twitch.tv/kraken/streams/" + user)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        return user_viewers(user)
    if (type(req) == int):
        print req
        print "wat. line 35 twitch_viewers"
    i = 0
    while (req.status_code != 200):
        print (str(req.status_code) + " viewerlist unavailable")
        try:
            req = requests.get("https://api.twitch.tv/kraken/streams/" + user)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            pass
        if (i > 15 and req.status_code == 422 and restart_on_failure):
            print "RESTARTING PROGRAM!!!!!!!!!!!!!!!!!!!!! 422 ERROR"
            restart_program()
        elif i > 15 and req.status_code == 422:
            print "quitting fn due to", user
            return 0
        if (req.status_code == 422):
            i += 1
    try:
        userdata = req.json()
    except ValueError:
        return user_viewers(user) #nope start over
    if ('stream' in userdata.keys()):
        viewers = 0
        if (userdata['stream']): # if the streamer is offline, userdata returns null
            viewers = userdata['stream']['viewers']
        if (viewers == 0):
            print user + " appears to be offline!"
        return viewers
    else:
        print str(userdata['status']) + " " + userdata['message'] + " " + userdata['error']
        print user + " is not live right now, or the API is down."
        return 0

