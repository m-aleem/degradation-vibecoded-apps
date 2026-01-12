# Inputs
|
|- Test/
|---|---README.md* (This file)
|---|---[test application name]/
|---|-----|---Output/
|---|-----|---[test application]_TestPlan.jmx
|---|-----|---pretest_notes.md (if applicable)
|---|-----|---<JMeter test files, such as CSVs> (if applicable)
|---|---monitor_docker.py
|---|---postprocess.py
|
|- applications
|---|---apps/
|---|-----|---[test application]/
|



# Experiment Steps

1) Bring up 4 Terminals and navigate to the directory containing this Test.md file. Set the environment variables as shown below, depending on the which test is being run. Note that this assumes the file structure as described above, so change as needed.

Select ONE of the following applications:
```
APP_NAME=gemini-2.5-flash-445
APP_NAME=gpt-oss-120b-446
APP_NAME=deepseek-chat-v3.1-241

APP_NAME=gemini-2.5-flash-418
APP_NAME=gpt-oss-120b-115
APP_NAME=deepseek-chat-v3.1-366
```

Set variables used below:
```
DURATION=100800
APP_DIR=`pwd`/../applications/apps/$APP_NAME
TEST_DIR=`pwd`/$APP_NAME
MONITOR_SCRIPT_DIR=`pwd`
JMETER_DIR=<path to JMeter such as /Users/.../apache-jmeter-5.6.3>
```

2) In Terminal 1, navigate to the application directory and ensure no docker containers are active.
```
cd $APP_DIR
docker-compose down
```

3) In Terminal 1, manually remove any database files/directories and then build and bring up docker.
```
rm -rf <database>
docker-compose build --no-cache
docker-compose up
```

4) In Terminal 2, run pre-test setup as described in any pretest notes.
```
cd $TEST_DIR
cat pretest_notes.md
```
Manually run the pretest setup, as needed.

5) In Terminal 2, being up the JMeter GUI, verify all durations are set as desired.
```
cd $JMETER_DIR
./bin/jmeter
```
Manually verify the JMeter test duration and ports via GUI, as needed.

6) In Terminal 3, navigate to the Python monitoring script directory (should just be pwd).
```
cd $MONITOR_SCRIPT_DIR
```

7) In Terminal 4, navigate to the Test Output directory. Delete or archive any existing files, if desired.
```
cd $TEST_DIR/Output
rm *
```

8) In Terminal 2, begin the JMeter test.
```
./bin/jmeter -n -t $TEST_DIR/*TestPlan.jmx -l $TEST_DIR/Output/jmeter_results.jtl
```

9) In Terminal 3, begin monitoring script.
```
CLEAN_APP_NAME="${APP_NAME/./}"
python3 monitor_docker_project.py --interval 60 --duration $DURATION --project $CLEAN_APP_NAME --csv $TEST_DIR/Output/monitor_results.csv
```

10) (Optionally) In Terminal 4, monitor the Output.

# Outputs
After the test completes, the following files will be available in $TEST_DIR/Output:

* monitor_results.csv - Output from the Python memory monitoring script
* jmeter_results.jtl - Output from the JMeter test

These files can be input to the `postprocess.py` script for visualization of results.