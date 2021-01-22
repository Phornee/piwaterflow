# PiWaterflow
This is a resilient watering system, executed in a Raspberry Pi to control irrigation valves using relays.
It's intended to be executed periodically (i.e. cron every 5 minutes).
- Requirements:
  -Raspberry Pi (any model)
  -Relays to control the valves
  -Optional control relay to enable alternative power inverter
- It supports 2 watering programs every day.
- This package fits with wwwaterflow, so that it can be controlled via HTTP page

```mermaid
sequenceDiagram
Alice ->> Bob: Hello Bob, how are you?
Bob-->>John: How about you John?
Bob--x Alice: I am good thanks!
Bob-x John: I am good thanks!
Note right of John: Bob thinks a long<br/>long time, so long<br/>that the text does<br/>not fit on a row.

Bob-->Alice: Checking with John...
Alice->John: Yes... John, how are you?
