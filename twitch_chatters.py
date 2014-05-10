import socket
import requests
import sys 
from twitch_viewers import user_viewers, removeNonAscii, user_total_views
import handle_twitter
from get_exceptions import get_exceptions
from chat_count import chat_count
import urllib2
import webbrowser

debug = False #debug mode with extraneous error messages and information
tweetmode = True #true if you want it to tweet, false if you don't
if len(sys.argv) > 1:
    tweetmode = False
alternative_chatters_method = False  #True if you want to use faster but potentially unreliable
                                     #method of getting number of chatters for a user
d2l_check = False #check dota 2 lounge's website for live matches?
user_threshold = 200   #initial necessity for confirmation
ratio_threshold = 0.16 #if false positives, lower this number. if false negatives, raise this number
expected_ratio = 0.7 #eventually tailor this to each game/channel. Tailoring to channel might be hard.

# these users are known to have small chat to viewer ratios for valid reasons
# example: chat disabled, or chat hosted not on the twitch site, or mainly viewed on 
#          front page of twitch
# type: list of strings: example: ["destiny", "scg_live"]
exceptions = get_exceptions()

#get_chatters2:
#   gets the number of chatters in user's Twitch chat, via chat_count
#   Essentially, chat_count is my experimental method that goes directly to 
#   a user's IRC channel and counts the viewers there. It is not yet proven to be 
#   correct 100% of the time.
#user is a string representing http://www.twitch.tv/<user>
def get_chatters2(user):
    chatters2 = 0
    try:
        chatters2 = chat_count(user)
    except socket.error as error:
        return get_chatters2(user)
    return chatters2

#user_chatters:
#   returns the number of chatters in user's Twitch chat
#user is a string representing http://www.twitch.tv/<user>
def user_chatters(user):
    chatters = 0
    chatters2 = 0
    try:
        req = requests.get("http://tmi.twitch.tv/group/user/" + user)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        return user_chatters(user)
    if (alternative_chatters_method):
        chatters2 = get_chatters2(user)
        if (chatters2 > 1):
            return chatters2
    try:
        while (req.status_code != 200):
            chatters2 = get_chatters2(user)
            if (alternative_chatters_method):
                if (chatters2 > 1):
                    return chatters2
            print "----TMI error", req.status_code, 
            print "getting", user + " (module returned %d)-----" %chatters2
            req = requests.get("http://tmi.twitch.tv/group/user/" + user)
        try:
            chat_data = req.json()
        except ValueError:
            return user_chatters(user)
        chatters = chat_data['chatter_count']
    except TypeError:
        print "recursing, got some kinda error"
        return user_chatters(user)
    return chatters

#dota2lounge_list:
#   returns the list of live Twitch streams embedded on dota2lounge.
#   this is useful because, at any given time, there could be tens of thousands
#   of users watching a Twitch stream through d2l, and I don't want to false positive these streams.
def get_dota2lounge_list():
    try:
        u = urllib2.urlopen('http://dota2lounge.com/index.php').read().split("matchmain")
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        print "D2L error :((("
        return []
    string = "LIVE</span>"
    list1 = filter(lambda x: string in x, u) 

    list2 = []
    string2 = "match?m="
    for item in list1:
        item = item.split("\n")
        for sentence in item:
            if (string2 in sentence):
                list2.append(sentence)

    d2l_list = []

    for item in list2:
        url = "http://dota2lounge.com/" + item.split("\"")[1]
        try:
            u2 = urllib2.urlopen(url).read().split("\n")
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            print "D2L error :((("
            return []
        list3 = filter(lambda x: "twitch.tv/widgets/live_embed_player.swf?channel=" in x, u2)
        for item in list3:
            item = item.split("channel=")[1].split("\"")[0].lower()
            d2l_list.append(item)
    return d2l_list

# very ugly web scraping :)))
def get_frontpage_users():
    try:
        u = urllib2.urlopen('http://www.twitch.tv',timeout=5).read().split('data-channel=')
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        print "Twitch frontpage error :((("
        return []
    users = []
    for channel in u:
        name = channel.split("'")[1]
        if name not in users:
            users.append(name)
    return users

#user_ratio:
#   returns the ratio of chatters to viewers in <user>'s channel
#user is a string representing http://www.twitch.tv/<user>
def user_ratio(user):
    print "checking", user, "ratio"
    chatters2 = 0
    exceptions = get_exceptions()
    if user in get_frontpage_users():
        print "nope,", user, "is on the front page of twitch."
        return 1
    if user in exceptions:
        print user, "is alright :)"
        return 1
    if d2l_check:
        d2l_list = get_dota2lounge_list()
        if (user in d2l_list):
            print user, "is being embedded in dota2lounge. nogo"
            return 1
    print "here1"
    chatters = user_chatters(user)
    if debug:
        chatters2 = get_chatters2(user)
    print "here2"
    viewers = user_viewers(user)
    print "here3"
    if (viewers != 0):
        maxchat = max(chatters, chatters2)
        ratio = float(maxchat) / viewers
        print user + ": " + str(maxchat) + " / " + str(viewers) + " = %0.3f" %ratio,
        if debug:
            print "(%d - %d)" %(chatters2, chatters),
        if chatters != 0:
            if debug:
                diff = abs(chatters2 - chatters)
                error = (100 * (float(diff) / chatters)) #percent error 
        else:
            return 0
        if debug and error > 6:
            print " (%0.0f%% error)!" %error,
            if error < 99 and diff > 10:
                print "!!!!!!!!!!!!!!!!!!!" #if my chatters module goes wrong, i want to notice it.
            if ratio > 1:
                webbrowser.open("BDB - ratio for "+user+" = %0.3f" %(ratio))
                print "????????????"
            else:
                print
        else:
            print
    else: 
        return 1 # user is offline
    return ratio

#game_ratio
#   returns the average chatter:viewer ratio for a certain game
#game is a string - game to search
def game_ratio(game):
    global tweetmode
    try:
        r = requests.get('https://api.twitch.tv/kraken/streams?game=' + game)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        print "uh oh caught exception when connecting. try again. see game_ratio(game)."
        return game_ratio(game)
    if (not r):
        return game_ratio(game)
    while (r.status_code != 200):
        print r.status_code, ", service unavailable"
        r = requests.get('https://api.twitch.tv/kraken/streams?game=' + game)
    try:
        gamedata = r.json()
    except ValueError:
        print "could not decode json. recursing"
        return game_ratio(game)
#TODO make a dictionary with keys as the game titles and values as the average and count
    count = 0 # number of games checked
    avg = 0
    while ('streams' not in gamedata.keys()):
        r = requests.get('https://api.twitch.tv/kraken/streams?game=' + game)
        while (r.status_code != 200):
            print r.status_code, ", service unavailable"
            r = requests.get('https://api.twitch.tv/kraken/streams?game=' + game)
        try:
            gamedata = r.json()
        except ValueError:
            print "couldn't json; recursing"
            return game_ratio(game)
    if len(gamedata['streams']) > 0:
        for i in range(0, len(gamedata['streams'])):
            viewers =  gamedata['streams'][i]['viewers']
            if viewers < user_threshold:
                break

            user = gamedata['streams'][i]['channel']['name'].lower() 
            name = "http://www.twitch.tv/" + user

            ratio = -1
            ratio = user_ratio(user)
            if (ratio == 0):
                print "ratio is 0... abort program?"
            handle_twitter.send_tweet(user, ratio, game, viewers, tweetmode, 
                                      ratio_threshold)
            avg += ratio
            count += 1
    else:
        print "couldn't find " + game + " :("
        return 0
    if count != 0:
        avg /= count
    # for the game specified, go through all users more than <user_threshold> viewers, find ratio, average them
    return avg

#remove_offline:
#   removes users from the twitter if they are no longer botting
def remove_offline():
    handle_twitter.destroy_offline()
    print
    print

#search_all_games:
#   loops through all the games via the Twitch API, checking for their average ratios
def search_all_games():
    try:
        topreq = requests.get("https://api.twitch.tv/kraken/games/top")
        while (topreq.status_code != 200):
            topreq = requests.get("https://api.twitch.tv/kraken/games/top")
        topdata = topreq.json()
    except ValueError:
        search_all_games()
    for i in range(0,len(topdata['top'])):
        game = removeNonAscii(topdata['top'][i]['game']['name'])
        print "__" + game + "__", 
        print "(tweetmode off)" if not tweetmode else ""
        ratio = game_ratio(game)
        print
        print "Average ratio for " + game + ": %0.3f" %ratio
        print
        print

#main loop 
try:
    handle_twitter.destroy_all_tweets()
    while True:
        search_all_games()
        remove_offline()
        print "looping back around :D"
except:
    handle_twitter.destroy_all_tweets() #sends the sentinel tweet automatically
    handle_twitter.on_crash()
    raise

