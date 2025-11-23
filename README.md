# Basketball Reference Scraper

Lightweight Python library for scraping NBA game data, box scores, rosters, injury reports, and schedules from [basketball-reference.com](https://www.basketball-reference.com/). It provides simple, structured functions for accessing NBA season data without needing to manually parse HTML or handle rate-limiting.

## Usage

This was originally a module in a school project. I created the web scraper to collect data to train an AI model to predict NBA match outcomes. I thought it would a cool first PyPi package.


```python

from basketball_ref_webscraper import *

#print(get_all_schedule(2005))               # Returns list of every planned match in the year's season.
print(get_roster('SAS', 2005))              # Returns all player's stats.
print(get_injury_report('SAS', 2026))       # Returns playerid of injured players.
matches = get_team_schedule('SAS', 2005)    # Returns list of every planned match for a particular team in the year's season.
print(get_boxscore(matches[0].match_link))  # Returns all basic boxscore stats.

```
