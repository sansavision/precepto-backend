import asyncio
import datetime
from datetime import timezone
import logging
import os
import sys
import json

# from peft import PeftModel, PeftConfig
# from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
# import torch
 

# Adjust the path to include the parent directory for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if (parent_dir not in sys.path):
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
from common.edgedb_client import EdgedbClient, DataclassEncoder
from common.queries.transcriptions.transcript_read_async_edgeql import transcript_read, TranscriptReadResult as TranscriptionMeta
from common.queries.transcriptions.transcript_update_async_edgeql import transcript_update
from agent_py_team4_x import SummarizationWorkflow
from common.token_utils import TokenValidator  # Add this import

# from common.models import TranscriptTemplate, TranscriptionMeta

logging.basicConfig(level=
        logging.INFO)

class SummarizationService:
    def __init__(self):
        self.db = EdgedbClient()
        self.client = self.db.client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.nats_client = NATSClient()
        self.llm_config = {
             "config_list": [{
                "model": "Gemma",
                "base_url": "http://localhost:5000/v1",
                "api_key": "e9cde95b10b268f36a93fe002aa97c39",
                "api_type": "openai",
                "temperature": 0,
                "top_p": 0.950,
                "max_tokens": 8192,
            }]
        }
        self.workflow = SummarizationWorkflow(llm_config=self.llm_config)
        self.token_validator = TokenValidator()  # Add this line
        
    

    # def generate_summary1(self, transcript, template, max_length=300, min_length=60):
    #     try:
    #         prompt = (
    #             f"Based on the following transcript and template, provide a structured summary.\n\n"
    #             f"Transcript:\n{transcript}\n\n"
    #             f"Template:\n{template}\n\n"
    #             "Instructions:\n"
    #             "1. Summarize each section of the transcript according to the template.\n"
    #             "2. If unsure about any part, mark it with ???.\n"
    #             "3. Precede each summary sentence with its timestamp in double brackets {{}}."
    #         )
            
    #         self.logger.debug(f"Constructed Prompt:\n{prompt}")

    #         # inputs = self.tokenizer(prompt, return_tensors='pt', truncation=True, max_length=2048).to(self.device)
    #         inputs = self.tokenizer(prompt, return_tensors='pt').to(self.device)
    #         self.logger.debug(f"Tokenized Inputs: {inputs}")

    #         output = self.model.generate(
    #             **inputs,
    #          max_new_tokens = max_length, 
    #          no_repeat_ngram_size=2, 
    #          pad_token_id=self.tokenizer.eos_token_id
    #         )
    #         # output = self.model.generate(
    #         #     **inputs,
    #         #     max_new_tokens=2048,
    #         #     # max_new_tokens=max_length,
    #         #     min_length=min_length,
    #         #     do_sample=False,
    #         #     top_p=0.95,
    #         #     top_k=10
    #         # )
    #         self.logger.debug(f"Generated Tokens: {output}")

    #         summary = self.tokenizer.decode(output[0], skip_special_tokens=True)

    #         print(f"Constructed Prompt:\n{prompt}")
    #         # print(f"Tokenized Inputs: {inputs}")
    #         # print(f"Generated Tokens: {output}")
    #         print(f"Decoded Summary:\n{summary}")

    #         self.logger.debug(f"Decoded Summary before splitting:\n{summary}")

    #         # Optional: Remove delimiter splitting if not necessary
    #         # summary = summary.split("|||\n")[-1] if "|||\n" in summary else summary

    #         return summary
    #     except Exception as e:
    #         self.logger.error(f"Error in generate_summary: {e}")
    #         return ""
    
    # def generate_summary(self, transcript, template, max_length=150, min_length=40):
    #     try:
    #         prompt = (
    #             f"based on this transcript {transcript} and this template {template}\n"
    #             "summarise the transcript carefully according to the structure, where you are unsure mark the part with ??? \n"
    #             "write the timestamps in double brackets at the start of each sentence {{}}"
    #         )
    #         inputs = self.tokenizer(prompt, return_tensors='pt', truncation=True, max_length=2048).to(self.device)
    #         output = self.model.generate(
    #             **inputs,
    #             max_new_tokens=max_length,
    #             min_length=min_length,
    #             do_sample=False,
    #             top_p=0.95,
    #             top_k=10
    #         )
    #         summary = self.tokenizer.decode(output[0], skip_special_tokens=True)
    #         summary = summary.split("|||\\n")[-1]
    #         return summary
    #     except Exception as e:
    #         self.logger.error(f"Error generating summary: {e}")
    #         return ""
    
    async def connect(self):
        try:
            await self.nats_client.connect()
            self.nats_client.kv_templates = await self.nats_client.setup_kv_bucket('templates')
            self.nats_client.kv_transcriptions = await self.nats_client.setup_kv_bucket('transcriptions')
            self.logger.info("Connected to NATS and KV stores 'templates' and 'transcriptions'")
        except Exception as e:
            self.logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def handle_completed_transcription(self, msg):
        try:
            data = json.loads(msg.data.decode())
            transcription_id = data.get('transcription_id')
            if not transcription_id:
                self.logger.error("No transcription_id provided")
                return

            self.logger.info(f"Processing summarization for transcription ID: {transcription_id}")
            
            # Get transcription from database
            transcription = await transcript_read(self.client, id=transcription_id)
            if not transcription:
                raise ValueError(f"Transcription {transcription_id} not found")

            # Parse template
            temp = json.loads(transcription.template.template)
            self.logger.debug(f"Parsed template: {json.dumps(temp, indent=2)}")

            async for result in self.workflow.run(transcription, temp):
                print("REsults ",result)
            # Update transcription with summary
                await transcript_update(
                    self.client,
                    id=transcription_id,
                    name=transcription.name,
                    # summary=summary,
                    summary=result,
                    status='not_signed',
                    backend_status='summarization_service',
                    next_backend_step='llm_service',
                    template_id=transcription.template.id,
                    backend_updated_at=datetime.datetime.now(timezone.utc)
                )

                # Notify next service
                await self.nats_client.publish('summarization.completed', 
                    json.dumps({"transcription_id": transcription_id}))
                
                self.logger.info(f"Summarization completed for transcription ID: {transcription_id}")

        except Exception as e:
            self.logger.error(f"Error processing summarization for transcription {data.get('transcription_id', 'unknown')}: {e}")
            raise


    def construct_template_string1(self, template_list):
        """
        Converts the list of template sections into a formatted string.
        """
        template_str = ""
        for section in template_list:
            title = section.get('title', 'Section')
            inclusion = section.get('inclusions', [''])[0]
            exclusion = section.get('exclusions', [''])[0]
            template_str += f"{title}: {inclusion} {exclusion}\n"
        self.logger.debug(f"Constructed Template String:\n{template_str}")
        return template_str

    def construct_template_string(self, template_list):
        """
        Converts the list of template sections into a formatted string.
        """
        template_str = ""
        for section in template_list:
            title = section.get('title', 'Section')
            inclusion = section.get('inclusions', [''])[0]
            template_str += f"{title}: {inclusion}\n"
        return template_str

    async def subscribe(self):
        try:
            await self.nats_client.subscribe('transcription.completed', self.handle_completed_transcription)
            self.logger.info("Subscribed to 'transcription.completed' subject")
        except Exception as e:
            self.logger.error(f"Subscription error: {e}")
            raise

    async def run(self):
        await self.connect()
        await self.subscribe()

        try:
            self.logger.info("SummarizationService is running.")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down SummarizationService...")
            await self.close()

    async def close(self):
        await self.nats_client.close()
        self.logger.info("SummarizationService has been shut down.")

if __name__ == '__main__':
    service = SummarizationService()
    asyncio.run(service.run())