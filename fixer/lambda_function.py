import json,boto3,os
from botocore.config import Config
from typing import Dict,List,Set

class ProjectAnalyzer:
    def __init__(self):
        self.bedrock=boto3.client('bedrock-runtime',region_name='us-west-2',config=Config(retries={'max_attempts':3},connect_timeout=10,read_timeout=120))
        self.file_cache:Dict[str,str]={}
        self.dependencies:Dict[str,Set[str]]={}
        
    def analyze_project(self,files:Dict[str,str],main_file:str,error:str)->dict:
        self.file_cache=files
        self._build_dependency_graph()
        affected_files=self._get_affected_files(main_file)
        project_context=self._build_project_context(affected_files)
        return self._analyze_with_context(main_file,error,project_context)
    
    def _build_dependency_graph(self):
        import_patterns=['import','from','require','include']
        for file_path,content in self.file_cache.items():
            self.dependencies[file_path]=set()
            lines=content.split('\n')
            for line in lines:
                line=line.strip()
                if any(p in line for p in import_patterns):
                    for other_file in self.file_cache.keys():
                        if os.path.basename(other_file).replace('.py','').replace('.js','') in line:
                            self.dependencies[file_path].add(other_file)
    
    def _get_affected_files(self,start_file:str)->Set[str]:
        affected=set([start_file])
        to_check=set([start_file])
        while to_check:
            current=to_check.pop()
            for file,deps in self.dependencies.items():
                if current in deps and file not in affected:
                    affected.add(file)
                    to_check.add(file)
        return affected
    
    def _build_project_context(self,files:Set[str])->str:
        context=""
        for file in files:
            context+=f"\nFile: {file}\n```\n{self.file_cache[file]}\n```\n"
        return context
    
    def _analyze_with_context(self,main_file:str,error:str,context:str)->dict:
        prompt=f"""Analyze this multi-file project focusing on {main_file} where an error occurred.
Project context (related files and their dependencies):
{context}
Error in {main_file}:
{error}
Provide analysis as JSON:
{{
"analysis":{{"main_file_issues":[],"cross_file_issues":[],"dependency_issues":[]}},
"fixes":[{{"file":str,"description":str,"position":{{"start":int,"end":int}},"code":str}}],
"refactoring_suggestions":[{{"description":str,"affected_files":[str],"changes":[{{"file":str,"old":str,"new":str}}]}}]
}}"""
        try:
            response=self.bedrock.invoke_model(modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',body=json.dumps({
                "anthropic_version":"bedrock-2023-05-31",
                "max_tokens":4096,
                "messages":[{"role":"user","content":[{"type":"text","text":prompt}]}],
                "temperature":0.3
            }))
            response_text=json.loads(response.get('body').read())['content'][0]['text']
            json_start=response_text.find('{')
            json_end=response_text.rfind('}')+1
            if json_start>=0 and json_end>0:
                return json.loads(response_text[json_start:json_end])
            return {"error":"Invalid response format"}
        except Exception as e:
            return {"error":str(e)}

def lambda_handler(event,context):
    try:
        body=event.get('body','{}')
        if isinstance(body,str):body=json.loads(body)
        files=body.get('files',{})
        main_file=body.get('main_file','')
        error=body.get('error','')
        analyzer=ProjectAnalyzer()
        result=analyzer.analyze_project(files,main_file,error)
        return {
            'statusCode':200,
            'headers':{'Content-Type':'application/json','Access-Control-Allow-Origin':'*'},
            'body':json.dumps({'response':json.dumps(result),'model':'Claude 3.5 Sonnet'})
        }
    except Exception as e:
        return {
            'statusCode':500,
            'headers':{'Content-Type':'application/json','Access-Control-Allow-Origin':'*'},
            'body':json.dumps({'error':str(e)})
        }