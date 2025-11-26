# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2025/11/19 16:43

from src.agents.toolkit.intent_classifier import classify_user_intent,_classify_chitchat_or_other


text = "嗯~这个？"
api_key = "sk-ec5eee92b8334405a5a3442a3a510221"

print(f"[智能体] 步骤1: 意图分类 - 用户输入: {text}")
label = classify_user_intent(text, api_key)
print(f"[智能体] 意图分类结果: {label}")
if label == "其他":
    new_label = _classify_chitchat_or_other(text)
    print(new_label)