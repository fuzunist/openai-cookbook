import openai
import streamlit as st
from termcolor import colored
from database import establish_redis_connection, fetch_redis_results
from config import CHAT_BOT_MODEL, PROMPTS_MODEL, INDEX_LABEL

redis_server = establish_redis_connection()

class Dialogue:
    def __init__(self, role, text):
        self.role = role
        self.text = text

    def to_dict(self):
        return {"role": self.role, "content": self.text}


class SearchBasedAssistant:
    def __init__(self):
        self.dialogue_history = []  

    def _fetch_assistant_reply(self, prompt):
        try:
            response = openai.ChatCompletion.create(
              model=CHAT_BOT_MODEL,
              messages=prompt,
              temperature=0.1
            )
            assistant_message = Dialogue(
                response['choices'][0]['message']['role'],
                response['choices'][0]['message']['content']
            )
            return assistant_message.to_dict()
        except Exception as e:
            return f'Request failed with exception {e}'

    def _retrieve_search_results(self, prompt):
        recent_query = prompt
        search_results = fetch_redis_results(
            redis_server, recent_query, 
            INDEX_LABEL
        )['result'][0]
        return search_results
        
    def interact_with_assistant(self, new_user_prompt):
        [self.dialogue_history.append(item) for item in new_user_prompt]
        assistant_reply = self._fetch_assistant_reply(self.dialogue_history)
        if 'searching for answers' in assistant_reply['content'].lower():
            query_extract = openai.Completion.create(
                model = PROMPTS_MODEL, 
                prompt=f'''
                Extract the user's latest question and the year for that question from this 
                conversation: {self.dialogue_history}. Extract it as a sentence stating the Question and Year."
            '''
            )
            redis_search_results = self._retrieve_search_results(query_extract['choices'][0]['text'])
            self.dialogue_history.insert(
                -1,{
                "role": 'system',
                "content": f'''
                Answer the user's question using this content: {redis_search_results}. 
                If you cannot answer the question, say 'Sorry, I don't know the answer to this one'
                '''
                }
            )
            assistant_reply = self._fetch_assistant_reply(self.dialogue_history)
            self.dialogue_history.append(assistant_reply)
            return assistant_reply
        else:
            self.dialogue_history.append(assistant_reply)
            return assistant_reply
            
    def display_conversation_history(self, highlight_assistant_responses=True):
        for dialogue in self.dialogue_history:
            if dialogue['role'] == 'system':
                continue
            prefix = dialogue['role']
            content = dialogue['content']
            print(colored(f"{prefix}:\n{content}", "green" if highlight_assistant_responses and dialogue['role'] == 'assistant' else None))
