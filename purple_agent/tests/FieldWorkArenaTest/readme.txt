Step 1:
running FieldWorkArenaTest/agent/fwa_green_agent.py

Step 2:
running DHAI_AgenticAI/tree/main/purple_agent/src/agent/server.py

Step 3:
running FieldWorkArenaTest/agent/client.py

Attention:
automatic_evaluation.py
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL"))

Current performace:
LLM: openai o4-mini
custom examples: Store_Manual_A.txt  WH_Products_Dispatch_2023_09_27_8AM_13_00_H_02_02.jpg  Cam003-Disposal0.mp4 English_Translation_FQ510-042_Wearing_Gloves.pdf
comparision protocol: fussy matching.
acc: 0.25
