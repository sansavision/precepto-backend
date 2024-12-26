import asyncio
import datetime
from datetime import timezone
import logging
import os
import sys
import json

from peft import PeftModel, PeftConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch
import pandas as pd

# Adjust the path to include the parent directory for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
from common.models import TranscriptTemplate, TranscriptionMeta

logging.basicConfig(level=logging.INFO)

class SummarizationService:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.nats_client = NATSClient()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Initialize the summarization model
        self.initialize_model()
        
        # Load tokenizer
        self.load_tokenizer()
        
    def initialize_model(self):
        try:
            self.logger.info("Loading PEFT configuration...")
            # peft_model_id = "NorGLM/NorGPT-369M-summarization-peft"
            peft_model_id = "NorGLM/NorGPT-369M-Instruction-peft"
            source_model_id = "NorGLM/NorGPT-369M"
            
            self.logger.info(f"Loading PeftConfig from {peft_model_id}...")
            config = PeftConfig.from_pretrained(peft_model_id)
            
            self.logger.info(f"Loading source model from {source_model_id}...")
            self.model = AutoModelForCausalLM.from_pretrained(
                source_model_id,
                device_map='balanced',
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
            
            self.logger.info(f"Loading PEFT model from {peft_model_id}...")
            self.model = PeftModel.from_pretrained(self.model, peft_model_id)
            self.model.to(self.device)
            self.model.eval()
            self.logger.info("Model loaded successfully.")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize model: {e}")
            raise
    
    def load_tokenizer(self):
        try:
            self.logger.info("Loading tokenizer...")
            source_model_id = "NorGLM/NorGPT-369M"
            tokenizer_max_len = 2048
            tokenizer_config = {
                'pretrained_model_name_or_path': source_model_id,
                'max_len': tokenizer_max_len
                # 'model_max_length': tokenizer_max_len
            }
            self.tokenizer = AutoTokenizer.from_pretrained(**tokenizer_config)
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.logger.info("Tokenizer loaded successfully.")
        except Exception as e:
            self.logger.error(f"Failed to load tokenizer: {e}")
            raise
    
    def load_default_template(self):
        try:
            template_path = os.path.join(os.path.dirname(__file__), 'default_template.json')
            with open(template_path, 'r', encoding='utf-8') as file:
                template_list = json.load(file)
            
            # Construct template string
            template_str = ""
            for section in template_list:
                template_str += f"{section['title']}: {section['inclusions'][0]}\n"
            
            return template_str
        except FileNotFoundError:
            self.logger.error("Default template JSON file not found.")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from default template: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error loading default template: {e}")
            raise
    

    def generate_summary1(self, transcript, template, max_length=300, min_length=60):
        try:
            prompt = (
                f"Based on the following transcript and template, provide a structured summary.\n\n"
                f"Transcript:\n{transcript}\n\n"
                f"Template:\n{template}\n\n"
                "Instructions:\n"
                "1. Summarize each section of the transcript according to the template.\n"
                "2. If unsure about any part, mark it with ???.\n"
                "3. Precede each summary sentence with its timestamp in double brackets {{}}."
            )
            
            self.logger.debug(f"Constructed Prompt:\n{prompt}")

            # inputs = self.tokenizer(prompt, return_tensors='pt', truncation=True, max_length=2048).to(self.device)
            inputs = self.tokenizer(prompt, return_tensors='pt').to(self.device)
            self.logger.debug(f"Tokenized Inputs: {inputs}")

            output = self.model.generate(
                **inputs,
             max_new_tokens = max_length, 
             no_repeat_ngram_size=2, 
             pad_token_id=self.tokenizer.eos_token_id
            )
            # output = self.model.generate(
            #     **inputs,
            #     max_new_tokens=2048,
            #     # max_new_tokens=max_length,
            #     min_length=min_length,
            #     do_sample=False,
            #     top_p=0.95,
            #     top_k=10
            # )
            self.logger.debug(f"Generated Tokens: {output}")

            summary = self.tokenizer.decode(output[0], skip_special_tokens=True)

            print(f"Constructed Prompt:\n{prompt}")
            # print(f"Tokenized Inputs: {inputs}")
            # print(f"Generated Tokens: {output}")
            print(f"Decoded Summary:\n{summary}")

            self.logger.debug(f"Decoded Summary before splitting:\n{summary}")

            # Optional: Remove delimiter splitting if not necessary
            # summary = summary.split("|||\n")[-1] if "|||\n" in summary else summary

            return summary
        except Exception as e:
            self.logger.error(f"Error in generate_summary: {e}")
            return ""
    
    def generate_summary(self, transcript, template, max_length=150, min_length=40):
        try:
            prompt = (
                f"based on this transcript {transcript} and this template {template}\n"
                "summarise the transcript carefully according to the structure, where you are unsure mark the part with ??? \n"
                "write the timestamps in double brackets at the start of each sentence {{}}"
            )
            inputs = self.tokenizer(prompt, return_tensors='pt', truncation=True, max_length=2048).to(self.device)
            output = self.model.generate(
                **inputs,
                max_new_tokens=max_length,
                min_length=min_length,
                do_sample=False,
                top_p=0.95,
                top_k=10
            )
            summary = self.tokenizer.decode(output[0], skip_special_tokens=True)
            summary = summary.split("|||\\n")[-1]
            return summary
        except Exception as e:
            self.logger.error(f"Error generating summary: {e}")
            return ""
    
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
            transcription_meta = TranscriptionMeta.from_json(msg.data.decode())
            recording_id = transcription_meta.id
            self.logger.info(f"Processing summarization for recording ID: {recording_id}")

            # Fetch user template from KV store
            if transcription_meta.template_id:
                template_entry = await self.nats_client.kv_get(self.nats_client.kv_templates, transcription_meta.template_id)
                if template_entry:
                    # Remove .value since template_entry is a string
                    transcript_template = TranscriptTemplate.from_json(template_entry)
                    template = self.construct_template_string(transcript_template.template)
                else:
                    self.logger.warning(f"Template not found for ID: {transcription_meta.template_id}")
                    template = self.load_default_template()
            else:
                template = self.load_default_template()

            # Generate summary
            summary_text = self.generate_summary(transcription_meta.transcript, template)

            # Update transcription meta
            transcription_meta.summary = summary_text
            transcription_meta.backend_status = 'summarization_service'
            transcription_meta.updated_at = datetime.datetime.now(timezone.utc).isoformat()

            # Update KV store
            await self.nats_client.kv_put(self.nats_client.kv_transcriptions, recording_id, transcription_meta.to_json())

            self.logger.info(f"Summarization complete for recording ID: {recording_id}")

        except Exception as e:
            self.logger.error(f"Error processing summarization for recording {recording_id}: {e}")


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