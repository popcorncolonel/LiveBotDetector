import time
from twython import Twython
from get_passwords import get_passwords, get_twitter_name
import twitter
from twitch_viewers import user_viewers
import requests

expected_ratio = 0.60

passes = get_passwords()

#must be a string - ex "day9tv"
twitter_name = get_twitter_name() 

APP_KEY =            passes[0]
APP_SECRET =         passes[1]
OAUTH_TOKEN =        passes[2]
OAUTH_TOKEN_SECRET = passes[3]

tweetter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
api = twitter.Api(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET) 

sentinel_msg = "Looks like no one is botting! :D"

#get_game_tweet:
#   tailors the name of the game (heh) to what is readable and short enough to tweet
#game is a string
def get_game_tweet(game):
    game_tweet = game.split(":")[0] #manually shorten the tweet, many of these by inspection
    if (game_tweet[:17] == "The Elder Scrolls"):
        game_tweet = "TES:" + game_tweet[17:] #TES: Online
    if (game_tweet == "League of Legends"):
        game_tweet = "LoL"
    if (game_tweet == "Call of Duty" and len(game.split(":")) > 1):
        game_tweet = "CoD:" + game.split(":")[1] #CoD: Ghosts, CoD: Modern Warfare
    if (game_tweet == "Counter-Strike" and len(game.split(":")) > 1):
        game_tweet = "CS: " 
        for item in game.split(":")[1].split(" "): 
            if (len(item) > 0):
                game_tweet += item[0] #first initial - CS:S, CS:GO
    if (game_tweet == "StarCraft II" and len(game.split(":")) > 1):
        game_tweet = "SC2: "
        for item in game.split(":")[1].split(" "):
            if (len(item) > 0):
                game_tweet += item[0] #first initial - SC2: LotV
    return game_tweet

def current_namelist():
    statuses = api.GetUserTimeline(twitter_name, count=200)
    if len(statuses) == 1 and statuses[0].text == sentinel_msg:
        return []
    else:
        l = []
        for status in statuses:
            l.append(status.text.split(" ")[0])
        return l


#send_tweet
#   if <user> is believed to be viewer botting, sends a tweet via the twitter module
#user is a string representing http://www.twitch.tv/<user>
#ratio is <user>'s chatter to viewer ratio
#game is the game they're playing (Unabbreviated: ex. Starcraft II: Heart of the Swarm)
#viewers is how many viewers the person has - can be used to get number of chatters, with ratio
def send_tweet(user, ratio, game, viewers, tweetmode, ratio_threshold):
    #name = "http://www.twitch.tv/" + user
    name = "twitch.tv/" + user
    if ratio < ratio_threshold:
        if tweetmode:
            print "Tweeting!"
        else:
            print "(Not actually Tweeting this):"
        chatters = int(viewers * ratio) 
        game_tweet = get_game_tweet(game)
        fake_viewers = int(viewers - (1 / expected_ratio) * chatters)
        estimate = "~" + str(fake_viewers) + " extra viewers of "+ str(viewers) + " total"
        tweet = user + " (" + game_tweet + ") " + estimate
        if (len(tweet) + 1 + max(22, len(name)) <= 140): #max characters in a tweet
            tweet = tweet + " " + name
        if not tweetmode:
            print "Not",
        print("Tweet text: '" + tweet + "'")
        while True:
            try:
                statuses = api.GetUserTimeline(twitter_name, count=200)
                break
            except requests.exceptions.ConnectionError:
                print "couldn't get my recent stati :((("
                time.sleep(5)
                pass
        rec_tweet_id = 0
        for status in statuses:
            # if deleting sentinel or "updating" a tweet
            if status.text == sentinel_msg or status.text.split(" ")[0] == user:
                rec_tweet_id = status.id
                break
        if rec_tweet_id != 0:
            print "Found recent tweet for", user + "! Updating!"
            while True:
                try:
                    api.DestroyStatus(rec_tweet_id)
                    break
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    print "couldn't tweet :( retrying"
                    time.sleep(5)
                    pass
        if tweetmode:
            while True:
                try:
                    tweetter.update_status(status=tweet)
                    break
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    print "couldn't tweet :( retrying"
                    time.sleep(5)
                    pass

def user_chatters(user, depth=0):
    if depth == 50:
        return None
    chatters = 0
    try:
        req = requests.get("http://tmi.twitch.tv/group/user/" + user)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        print user+"__"
        return user_chatters(user, depth=depth+1)
    try:
        while req.status_code != 200:
            print "----TMI error", req.status_code, "getting", user + "-----"
            time.sleep(1)
            req = requests.get("http://tmi.twitch.tv/group/user/" + user)
        try:
            chat_data = req.json()
        except ValueError:
            return user_chatters(user)
        chatters = chat_data['chatter_count']
    except TypeError:
        print "recursing, got some kinda error"
        return user_chatters(user, depth=depth+1)
    except:
        print "error getting chatters."
        return user_chatters(user, depth=depth+1)
    return chatters

def user_ratio(user):
    chatters = user_chatters(user)
    if chatters == None:
        return 1 #some error occurred. streamer offline? twitch down?
    viewers = user_viewers(user)
    if viewers and viewers != 0:
        ratio = float(chatters) / viewers
        if chatters == 0:
            return 0
    else: 
        return 1 # user is offline
    return ratio

def send_sentinel_tweet():
    tweetter.update_status(status=sentinel_msg)

#deletes offline users from the timeline
def destroy_offline():
    stati = api.GetUserTimeline(twitter_name, count=200)
    if len(stati) == 1:
        if stati[0].text == sentinel_msg:
            return
    for status in stati:
        name = status.text.split(" ")[0]
        if user_ratio(name) > (0.17) or user_viewers(name) < 200:
            print name + " appears to have stopped botting! deleting tweet."
            try:
                api.DestroyStatus(status.id)
            except twitter.TwitterError:
                time.sleep(5)
                pass
    if len(api.GetUserTimeline(twitter_name, count=200)) == 0:
        send_sentinel_tweet()

def destroy_all_tweets():
    try:
        stati = api.GetUserTimeline(twitter_name, count=200)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        time.sleep(3)
        return destroy_all_tweets()
    while len(stati) != 0:
        for status in stati:
            try:
                api.DestroyStatus(status.id)
                print "deleted status", status.text
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                print status
                print status.id
                print status.text
                destroy_all_tweets()
                break
        try:
            stati = api.GetUserTimeline(twitter_name, count=200)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            continue

crash_msg = "Looks like this bot isn't running :/\n(It either crashed or I turned it off for some reason.)" 
def on_crash():
    tweetter.update_status(status=crash_msg)

