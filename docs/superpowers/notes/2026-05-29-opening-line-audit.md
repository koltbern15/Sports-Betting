# Opening-Line Audit — 2026-05-29

## Coverage

source  season  rows
   aus    2006   267
   aus    2007   267
   aus    2008   266
   aus    2009   267
   aus    2010   267
   aus    2011   266
   aus    2012   267
   aus    2013   267
   aus    2014   267
   aus    2015   267
   aus    2016   267
   aus    2017   267
   aus    2018   267
   aus    2019   267
   aus    2020   269
   aus    2021   285
   aus    2022   284
   aus    2023   285
   aus    2024   285
   sbr    2007   204
   sbr    2008   204
   sbr    2009   220
   sbr    2010   223
   sbr    2011   221
   sbr    2012   221
   sbr    2013   218
   sbr    2014   223
   sbr    2015   220
   sbr    2016   220
   sbr    2017   251
   sbr    2018   251
   sbr    2019   251
   sbr    2020   264
   sbr    2021   285

## Overlap Agreement (2013–2021)

Games with both sbr + aus rows: 2183

| Market  | tol=0.5 | tol=1.0 |
| ------- | ------- | ------- |
| Spread  | 0.6102  | 0.7490  |
| Total   | 0.6633  | 0.8236  |

### Worst 10 spread disagreements

 season            home_team            away_team  sbr_spread  aus_spread  spread_diff
   2013    Green Bay Packers  Philadelphia Eagles       -10.0         1.0         11.0
   2017     Los Angeles Rams  San Francisco 49ers         3.5        -6.5         10.0
   2020   Kansas City Chiefs     Cleveland Browns         0.0       -10.0         10.0
   2017 New England Patriots Jacksonville Jaguars         0.0        -9.5          9.5
   2020     Tennessee Titans  Pittsburgh Steelers        -7.0         2.0          9.0
   2020        Buffalo Bills       Miami Dolphins         5.5        -3.5          9.0
   2019    Arizona Cardinals  San Francisco 49ers         0.0         8.0          8.0
   2019    Minnesota Vikings        Chicago Bears         7.0        -1.0          8.0
   2019       Houston Texans       Denver Broncos        -0.5        -8.0          7.5
   2014 New England Patriots        Buffalo Bills        -3.5       -10.5          7.0

### Worst 10 total disagreements

 season          home_team             away_team  sbr_total  aus_total  total_diff
   2021 Cincinnati Bengals  Jacksonville Jaguars       10.5       45.5        35.0
   2019     Houston Texans        Denver Broncos        8.0       41.0        33.0
   2020   Tennessee Titans  Jacksonville Jaguars       11.0       43.0        32.0
   2017      Buffalo Bills    Indianapolis Colts       13.5       39.5        26.0
   2021  Minnesota Vikings   Pittsburgh Steelers       30.0       45.0        15.0
   2013     Denver Broncos Washington Commanders       52.0       59.0         7.0
   2013      Chicago Bears      Baltimore Ravens       47.0       40.0         7.0
   2021   Cleveland Browns    Cincinnati Bengals       37.0       44.0         7.0
   2013     Denver Broncos  Jacksonville Jaguars       47.0       53.0         6.0
   2013  Carolina Panthers       Atlanta Falcons       41.0       47.0         6.0

## Closer Sanity

### Movement stats (close − open)

| Market | n   | mean  | stdev |
| ------ | --- | ----- | ----- |
| Spread | 4570 | 0.123 | 1.724 |
| Total  | 4570 | -0.332 | 7.738 |

### Spread outliers (|close − open| > 7.0): 19 games

 season             home_team             away_team  open_spread_home  spread_home_close
   2012      Seattle Seahawks     Green Bay Packers              -7.0                3.5
   2024      Los Angeles Rams      Seattle Seahawks              -2.5                7.5
   2024        Denver Broncos     Carolina Panthers              -4.5              -13.0
   2023  Jacksonville Jaguars      Baltimore Ravens               5.5               -4.0
   2023    Cincinnati Bengals   Pittsburgh Steelers              -5.5                2.0
   2023         New York Jets        Miami Dolphins              -2.5                9.5
   2023        Dallas Cowboys       New York Giants              -9.5              -17.5
   2022   Philadelphia Eagles       New York Giants              -1.5              -17.0
   2022 Washington Commanders        Dallas Cowboys              -4.5                7.5
   2022      Tennessee Titans        Dallas Cowboys               3.0               14.0
   2022        Dallas Cowboys    Cincinnati Bengals              -1.5                7.0
   2021      Los Angeles Rams   San Francisco 49ers              -6.0                3.5
   2021      Cleveland Browns     Las Vegas Raiders              -6.5                1.0
   2021   San Francisco 49ers     Arizona Cardinals               2.5               -5.5
   2020   Philadelphia Eagles Washington Commanders              -1.0                6.5
   2020        Denver Broncos    New Orleans Saints               6.0               14.5
   2017      Los Angeles Rams   San Francisco 49ers              -6.5                6.0
   2017   Pittsburgh Steelers      Cleveland Browns             -16.0               -5.0
   2015    Kansas City Chiefs         Detroit Lions              -6.0                3.0

## ML Status

source  total_rows  ml_rows
   aus        5144     5144
   sbr        3476        0
