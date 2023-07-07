import yfinance as yf
import os
import time
import datetime
from collections import Counter
import praw
import openai

openai.api_key = "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"
requests_made = 0
RATE_LIMIT = 59

start = time.time()

reddit = praw.Reddit(client_id='X198MSPE2eFkgkrq88sUrg', client_secret='g0ton864qCrg-6GXtYLSKjG6mPPB8Q',
                     user_agent='myapp')

subreddit = reddit.subreddit('wallstreetbets')

feed = subreddit.hot(limit=100)

bot_usernames = ["VisualMod", "AutoModerator"]

filename = "text_data.txt"
skip_data = None
skip_analysis = None
if os.path.isfile(filename):
    while skip_data is None:
        user_input = input("Do you want to skip data collection? (yes/no): ")
        if user_input.lower() == "yes":
            skip_data = True
        elif user_input.lower() == "no":
            skip_data = False
        else:
            print("Invalid response. Please enter 'yes' or 'no'.")

while skip_analysis is None:
    user_input = input("Do you want to skip sentiment analysis? (yes/no): ")
    if user_input.lower() == "yes":
        skip_analysis = True
    elif user_input.lower() == "no":
        skip_analysis = False
    else:
        print("Invalid response. Please enter 'yes' or 'no'.")


def create_unique_file(filename):
    if not os.path.exists(filename):
        with open(filename, "w"):
            pass
        print(f"Created file: {filename}")
        return filename
    else:
        # File exists, add number at the end
        base_name, extension = os.path.splitext(filename)
        counter = 1
        while os.path.exists(f"{base_name}_{counter}{extension}"):
            counter += 1
        new_filename = f"{base_name}_{counter}{extension}"
        with open(new_filename, "w"):
            pass
        print(f"Created file: {new_filename}")
        return new_filename


filename = create_unique_file("log.txt")


if not skip_data or skip_data is None:
    with open("text_data.txt", "a", encoding="utf8") as data:
        data.truncate(0)
        n = 1
        for submission in feed:
            print(str(n) + ": " + submission.title)
            n += 1
            submission.comments.replace_more(limit=None)  # Retrieve all comments
            comments = submission.comments.list()
            for comment in comments:
                if comment.author not in bot_usernames:
                    merged_comment = comment.body.replace("\n", " ")
                    data.write(merged_comment + "\n")


def is_ticker(string):
    ticker = yf.Ticker(string)

    try:
        info = ticker.info
    except:
        return False

    return True


def update_request_count():
    global requests_made
    requests_made += 1

    if requests_made >= RATE_LIMIT:
        requests_made = 0
        print("Rate limit hit. Sleeping for 60 seconds.")
        time.sleep(60)


def sentiment_analysis(ticker, text):
    prompt = """Decide whether an investing comment is bullish, bearish, or neutral for a given ticker. Respond with 
    bullish, bearish, or neutral. 

    Ticker: %s.
    Text:%s."""

    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=prompt % (ticker, text),
        temperature=0,
        max_tokens=64
    )

    update_request_count()

    response_text = response.get("choices")[0].get("text").strip()

    if "bullish" in response_text:
        return "bullish"

    elif "bearish" in response_text:
        return "bearish"

    elif "neutral" in response_text:
        return "neutral"
    else:
        raise ValueError("Unexpected result: %s" % response_text)


def get_stock_tickers(text):
    prompt = """Decide whether text mentions a stock ticker. Respond with the name of the ticker(s) if yes and \"none\" 
    if no. If there are multiple tickers, separate them with commas. 

    Text:%s."""

    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=prompt % text,
        temperature=0,
        max_tokens=64
    )

    update_request_count()

    response_text = response.get("choices")[0].get("text").strip()

    return response_text.split(", ")


tickers = []
bullish = []
bearish = []
neutral = []
overall = []

if not skip_analysis:
    with open('text_data.txt', 'r', encoding='utf8') as data:
        for line in data:
            found = get_stock_tickers(line)
            if found[0] != "none":
                for i in found:
                    if is_ticker(i):
                        with open(filename, "a", encoding="utf8") as log:
                            sentiment = sentiment_analysis(i, line)
                            if sentiment == "bullish":
                                log.write("Possible bullish sentiment for " + i + ": " + line)
                                bullish.append(i)
                            elif sentiment == "bearish":
                                log.write("Possible bearish sentiment for " + i + ": " + line)
                                bearish.append(i)
                            elif sentiment == "neutral":
                                log.write("Possible neutral sentiment for " + i + ": " + line)
                                neutral.append(i)


def count_and_sort(lst):
    counts = Counter(lst)
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    result = [f"{count} {item}" for item, count in sorted_counts]
    return result


def sort_list_by_number_descending(lst):
    sorted_lst = sorted(lst, key=lambda x: int(x.split()[0]), reverse=True)
    return sorted_lst


def find_value(array, ticker):
    for i in array:
        if i.split()[1] == ticker:
            return int(i.split()[0])
    return 0


for i in tickers:
    ticker = i.split()[1]
    value = find_value(bullish, ticker) - find_value(bearish, ticker)

    if value == 0 and i in neutral:
        overall.append(str(value) + " " + ticker)
        continue

    overall.append(str(value) + " " + ticker)


bullish = count_and_sort(bullish)
bearish = count_and_sort(bearish)
neutral = count_and_sort(neutral)
overall = sort_list_by_number_descending(overall)

print("BULLISH: " + str(bullish))
print("BEARISH: " + str(bearish))
print("NEUTRAL: " + str(neutral))
print("OVERALL: " + str(overall))

elapsed = time.time() - start
elapsed_time = datetime.timedelta(seconds=int(elapsed))
elapsed_str = str(elapsed_time)
print("Time elapsed: " + elapsed_str)
