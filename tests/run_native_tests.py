import argparse,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True);p.add_argument('--compiler-jar');args=p.parse_args()
jar=Path(args.json_jar).resolve()
with tempfile.TemporaryDirectory() as folder:
 sources=[ROOT/'android/app/src/main/java/ru/personal/planner/ReminderCalculator.java',ROOT/'tests/ReminderCalculatorTest.java']
 compiler=['java','-jar',str(Path(args.compiler_jar).resolve()),'-8'] if args.compiler_jar else ['javac','-source','8','-target','8']
 subprocess.run([*compiler,'-encoding','UTF-8','-classpath',str(jar),'-d',folder,*map(str,sources)],check=True)
 subprocess.run(['java','-cp',folder+os.pathsep+str(jar),'ReminderCalculatorTest'],check=True)
