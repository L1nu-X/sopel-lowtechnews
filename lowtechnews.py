import sopel.module
import requests
import urllib.parse
from datetime import datetime as dt
import dateparser
import json

baseUrl = "https://news.lowtech.io"
apiUrl = "{}/api/v1".format(baseUrl)
searchUrl = "{}/search/".format(baseUrl)
latest_max_results = 3
trending_last_hours = 24
trending_max_words = 20

class ApiResponse(object):
        def __init__(self, code, message, payload=None, metadata=None):
            self.code = code
            self.message = message
            self.payload = payload
            self.metadata = metadata

        def __str__(self):
            return "<ApiResponse {}:'{}' {}/>".format(self.code, self.message, self.payload)

@sopel.module.commands('trending')
@sopel.module.example('.trending', 'Gets a list of trending words from the news cycle in the last 12 hours and 15 words')
def trending_words(bot, trigger):
    """Gets any over-riding values in the command group"""

    # Set up the number of hours and words to pass to the API call
    cmd_hours = trending_last_hours
    cmd_words = trending_max_words
    supplied_values = []

    # Check if any overriding values were passed in the command, such that
    # the command is ".trending 24 10"
    supplied_hw_combo = trigger.group(2)
    if supplied_hw_combo != None:
        supplied_values = supplied_hw_combo.strip().split(" ")

    if len(supplied_values) > 2:
        say_error(bot, trigger.nick, "You may supply a maximum of 2 values for trending: '.trending <num-hours> <num-words>'. Using default values instead.")
    else:
        if len(supplied_values) >= 1:
            cmd_hours = int(supplied_values[0])

        if len(supplied_values) == 2:
            cmd_words = int(supplied_values[1])

    api_resp = load_trending_words(cmd_hours, cmd_words)
    if api_resp.code == 200:
        words = api_resp.payload;
        if len(words) > 0:
            say_words(bot, trigger.nick, cmd_hours, cmd_words, words)
        else:
            say_error(bot, trigger.nick, "No words were returned for your trending 'number of hours' and 'number of words' range")
    else:
        say_error(bot, trigger.nick, api_resp.metadata["message"])



@sopel.module.commands('n')
@sopel.module.example('.n', 'Gets a list of news items from lowtech news')
def news_list(bot, trigger):
    """Gets a list of the top news from lowtech.io"""
    cmd = trigger.group(2)

    if cmd and cmd[:1] == "#":
        # Identifies that we are looking for a specific entry id and
        # looks up that id
        api_resp = load_specific(cmd[1:].strip())
        if api_resp.code == 200:
            entries = api_resp.payload["results"]
            if len(entries) > 0:
                say_entry(bot, entries.pop())
            else:
                say_error(bot, trigger.nick, "The specific ID '{}' was not found".format(cmd[1:]))
        else:
            error_message = "Error {}: {}"
            if "message" not in api_resp.metadata:
                error_message = error_message.format(api_resp.code, "Could not retrieve entry")
            else:
                error_message = error_message.format(api_resp.code, api_resp.metadata["message"])
                                                     
            say_error(bot, trigger.nick, error_message)
    else:
        # Does a search based on the supplied term against the API
        api_resp = load_search_result(cmd)
        if api_resp.code == 200:
            entries = api_resp.payload["results"]
            display_results = min(len(entries), latest_max_results)
            max_results = int(api_resp.metadata["max_results"])

            # Only show the more link when we have additional results that will not be shown
            more_link = ""
            if display_results < max_results:
                more_link = "More: {}{}".format(searchUrl, urllib.parse.quote(cmd))

            if max_results == 0:
               say_info(bot, "{}: ain't got shit m_8eightEIGHT.".format(trigger.nick))
            else:
               # Output header message and each of the entries
               say_info(bot, "{}: Displaying {} newest entries from {} results. {}".format(trigger.nick, display_results, max_results, more_link))
               for x in range(0, display_results):
                   say_entry(bot, entries[x])
        else:
            say_error(bot, trigger.nick, api_resp.metadata["message"])


@sopel.module.commands('v', 'vote')
@sopel.module.example('.v list of topics up', 'Votes a certain topic up or down. Supply a space-separated list of topic(s) and end with the term 'up' or 'down' to register: '.vote <topic(s)> [up|down]')
def vote_topic(bot, trigger):
    """Votes a topic up or down on lowtech.io"""

    supplied_words = []
    supplied_text = trigger.group(2)
    if supplied_text != None:
        supplied_words = supplied_text.strip().split(" ")

    topic_error_text = "You need to supply topic(s) and end with the term 'up' or 'down' to register: '.vote <topic(s)> [up|down]'"
    if len(supplied_words) < 2:
        say_error(bot, trigger.nick, topic_error_text)
    else:
        # Check that the last word is one of two specific words
        voting_word = str(supplied_words[-1]).lower()
        if voting_word not in ["up", "down"]: 
            say_error(bot, trigger.nick, topic_error_text)
        else: 
            topics = supplied_words[:-1] 
            payload = {"vote":voting_word,"topics":topics,"nick":trigger.nick,"user":trigger.user}
            api_resp = post_vote_registration(payload)
            if api_resp.code == 200:
                say_info(bot, "{}: {}".format(trigger.nick, api_resp.metadata["message"]))
            else:
                say_error(bot, trigger.nick, api_resp.metadata["message"])
            


# ------- SUPPORT FUNCTIONS ------------
def load_specific(entry_id):
    """ Loads a specific entry id from the API """
    apiLoadSpecificUrl = "{}{}/{}".format(apiUrl, "/id", entry_id)
    return parse_news_api_response(requests.get(apiLoadSpecificUrl))

def load_list(initial_offset, number_of_entries):
    """ Loads a list of entries from the API baed on the initial page and the number of entries to load """
    apiLoadListUrl = "{}{}/{}/{}".format(apiUrl, "/latest", initial_offset, number_of_entries)
    return parse_news_api_response(requests.get(apiLoadListUrl))

def load_search_result(search_term):
    apiGetSearchResult = "{}{}/{}".format(apiUrl, "/search", urllib.parse.quote(search_term))
    return parse_news_api_response(requests.get(apiGetSearchResult))

def load_trending_words(cmd_hours, cmd_words):
    apiLoadTrendingUrl = "{}{}?num_hours={}&num_words={}".format(apiUrl, "/info/word-cloud", cmd_hours, cmd_words)
    return parse_news_api_response(requests.get(apiLoadTrendingUrl))

def post_vote_registration(payload):
    voteRegistrationUrl = "{}{}".format(apiUrl, "/vote")
    return parse_news_api_response(requests.post(voteRegistrationUrl, json=payload))

def parse_news_api_response(api_response):
    """ Gets a list of news entries from a json response """
    payload_key = "payload"
    metadata_key = "metadata"
    message_key = "message"
    code_key = "code"

    response = None
    code = 200
    message = "Okay"
    payload = {}
    metadata = {}

    try:
        response = api_response.json()
    except json.decoder.JSONDecodeError:
        response = None
        code = api_response.status_code
        message = api_response.text

    if response is not None:

        if payload_key in response:
            payload = response[payload_key]

        if metadata_key in response:
            metadata = response[metadata_key]

        if code_key in response:
            code = response[code_key]

    if message_key in metadata:
        message = metadata[message_key]
    else:
        metadata[message_key] = message

    return ApiResponse(code, message, payload, metadata)

def say_info(bot, info_text):
    """ Outputs a specific bit of infomational text for the channel """
    bot.say(info_text)

def say_entry(bot, entry):
    """ Outputs the entry in standard form to the IRC channel """
    entry_date = get_date(entry)
    if entry_date is None:
        response_text = "#{}: {} {}".format(entry["id"], entry["title"], entry["href"])        
    else:
        response_text = "#{} ({}): {} {}".format(entry["id"], entry_date.strftime("%Y-%m-%d"), entry["title"], entry["href"])
    bot.say(response_text)

def format_words(words_array):
    """ Extracts the word value from the dictionary and inserts into an array for further use """
    words = []
    for i in range(len(words_array)):
        words.append(words_array[i]["word"])

    word_list = ", ".join(words)
    return word_list

def say_words(bot, nick, num_hours, num_words, words):
    """ Outputs the set of words in standard form to the IRC channel """
    response_title = "{}: Trending {} words over the last {} hours".format(nick, num_words, num_hours)
    word_list = format_words(words)
    response_text = "{}: {}".format(response_title, word_list)
    bot.say(response_text)

def say_error(bot, nick, entry):
    """ Outputs an error message in standard form to the IRC channel """
    response_text = "{}: Error => {}".format(nick, entry)
    bot.say(response_text)

def get_date(entry):
    """ Parses the entry if there is a date_added value and returns a datetime object"""
    entry_date = None
    if "date_added" in entry:
        entry_date = dateparser.parse(entry["date_added"])

    return entry_date
        
if __name__ == "__main__":

    # Test the API loading up a specific identifier
    specific_id = "424347"
    print("Looking up '{}':".format(specific_id))
    result = load_specific(specific_id)
    if result.code == 200:
        print("Successfully loaded #{}".format(specific_id))
        entry_date = get_date(result.payload["results"][0])
        print("\t Date: {}".format(entry_date.strftime("%Y-%m-%d")))
        print("\t {}...".format(str(result)[:120]))
    else:
        print(result)

    # Test the API loading via a search string
    search_term = "candy crush"
    print("Looking up '{}':".format(search_term))
    result = load_search_result(search_term)
    if result.code == 200:
        print("Successfully loaded search results with {} search results".format(result.metadata["max_results"]))
        print("\t {}...".format(str(result)[:120]))
    else:
        print(result)

    # Test the API loading trending results
    num_hours = 48
    num_words = 15
    print("Looking up trending words over the last {} hours and requesting {} words".format(num_hours, num_words))
    result = load_trending_words(num_hours, num_words)
    if result.code == 200:
        words = format_words(result.payload)
        print("Successfully loaded {} trending words:'".format(len(result.payload)))
        print("\t {}".format(words))
    else:
        print(result)

            

