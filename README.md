# Auto load balancer
This is a new auto load balancing tool to keep the network out of a congested state across all beams.
- load_balance_main.py
  - balance_status.py
    - write_balance_data.py
  - trigger_load_balance.py
    - load_balance.py
  - case_driver.py
  
## load_balance_main.py
This is the core script that calls each other action.
### balance_status.py
This script will get called if there are any cases in res/open_cases.txt. Cases will be removed from open_cases once all cases have been closed and the status of the terminals have been checked and stored in the database.
### trigger_load_balance.py
This script is called next to trigger a new set of load balances. 
### case_driver.py
This script will open cases on viasats website for each of the load balances that were performed
