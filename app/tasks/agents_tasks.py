
## go through units code given,pewrform agent tasks, insert the result todb, markthe unit as complete
from crewai import Agent, Task, Crew, LLM
from typing import Type, Any, Optional
from crewai.tools import BaseTool
from crewai_tools import FileWriterTool
from datetime import datetime
from pydantic import BaseModel, Field


gemini_key = os.getenv("GEMINI_API_KEY")

llm = LLM(model="gemini/gemini-1.5-flash", api_key=gemini_key)


class QuestionVectorSearchToolInput(BaseModel):
    """Input schema for the QuestionVectorSearchTool."""
    query: Optional[dict] = Field(
        None, description="The search query to find relevant forum posts")


class QuestionVectorSearchTool(BaseTool):
    name: str = "question_vector_search_tool"
    description: str = (
        "Searches the student forum post knowledge base. Use this to find submissions based on content similarity using a 'query'. "
    )
    args_schema: Type[BaseModel] = QuestionVectorSearchToolInput
    vectorstore: Any = None
    collection_name: str = ""

    def __init__(self, database, index_name: str, collection_name: str, threshold=0.1, **kwargs):
        super().__init__()
        self.vectorstore = database.Index(index_name)
        self.collection_name = collection_name
        self.threshold = threshold

    def _run(self, query: str = None, id=None, days_ago: int = 7, **kwargs):
        # Perform the vector search using the vectorstore
        # filter out the probability less than 0.2
        if query is None:
            return [{"error": "Tool requires query to search for similar questions."}]

        if query:
            results = self.vectorstore.search(namespace=self.collection_name, query={
                "inputs": {"text": query.get("content", "")},
                "top_k": 3,
            }, fields=["id", "content", "metadata"], rerank={
                "model": "cohere-rerank-3.5",
                "rank_fields": ["content"]
            })
        hits = results.get("result", {}).get("hits", [])
        [hit for hit in hits if hit.get("_score", 0) > self.threshold]
        return results.get("result", [])
 
rag_tool = QuestionVectorSearchTool(
    database=pc,
    index_name=INDEX_NAME,
    collection_name="22913",
)
themeExtractorAgent = Agent(
    role= "You are a high education university tutor for {unit}  " \
    "So that you can help identify common questions" ,
    goal = "Extract the common theme of the questions students asked on the forum" \
    "This will then be use to help resolve their issues including creating a FAQ or make modification on certain assessment specification ", 
    backstory= "You are a high education university tutor that is good at identifying common repeated theme amongts the questions student has asked."
    "Your task is to identify these and determine the underlying theme or point of confusion that should be address.",
    verbose= True,
    allow_delegation=False,
    llm=llm
    )
themeExtractorTask = Task(
    description= "Extract the common theme of the questions students asked on the forum by going through a list of top questions {questions} seperated by , one by one identified through hdb clustering students questions on forum"\
    "Make use of the given questions as a query to the vector store to retrieve top similar semantic questions. Identify if they are related, if they are group them and generate a summary",
    expected_output="Generate a list of themes and a summary of the questions identified"
    "The summary should be relevant to the {unit}",
    tools=[rag_tool],
    agent=themeExtractorAgent,
)

faqWriterAgent = Agent(
    role="You are the chief lecturer at a university for {unit}  "
    "So that you can help identify common questions",
    goal="Generate a clear and concise FAQ draft using the common theme of the questions students asked on the forum. you dont need to provide the answer, this will be manage be the chief lecturer",
    backstory="An expert technical writer specializing in educational content, creating helpful answers for students.",
    verbose=True,
    allow_delegation=False,
    llm=llm
)
faqWritingTask = Task(
    description="Given a list of common themes identified in students questions generate a detail faq that can address these questions. Make use of the content {content} and assessment to help generate the faq."
    "Theres no need to provide an answer, the questions will be used be the chief lecturer where he can draft up accurate response"
    "Make use of the given questions as a query to the vector store to retrieve top similar semantic questions. Identify if they are related, if they are group them and generate a summary",
    expected_output="bullet points of questions that address all the common themes identified, and a short answer that can help the tutor address them",
    tools=[rag_tool, FileWriterTool()],
    agent=faqWriterAgent,
)

reportWriterAgent = Agent(
    role="You are the chief lecturer at a university for {unit}  "
    "So that you can help identify common questions",
    goal="Synthesize all findings (themes, frequencies, assessment links, FAQ draft) into a summary report for the teaching team."
    " Highlight trends, potential blockers, and areas needing attention.",
    backstory="You are trying to make improvement to the unit weekly. Creates insightful executive summaries for the teaching team, focusing on actionable insights from student data.",
    verbose=True,
    allow_delegation=False,
    llm=llm
)
reportWritingTask = Task(
    description="Compile a summary report for the teaching team based on this week's analysis. Include: Overview of submission volume, list of major themes identified (with frequency), "
    "their links to assessment topics, highlights of common misconceptions or blockers, and the draft FAQ section. "
    "Structure it for easy readability by educators.",
    expected_output="A well-structured weekly report summarizing student question trends and the generated FAQ.",
    tools=[FileWriterTool()],
    agent=reportWriterAgent,
)

question_crew = Crew(agents=[themeExtractorAgent, faqWriterAgent, reportWriterAgent], tasks=[
                     themeExtractorTask, faqWritingTask, reportWritingTask], verbose=True)

question_crew.kickoff(input)


def run_agent_tasks(unit_id: str):
    """
    Run the agent tasks for a specific unit.
    """
    # get the clustered questions for the unit from db
    questions = db.get_clustered_questions(unit_id)
    # Fetch the relevant data for the unit
    unit_data = db.get_unit_data(unit_id)
    input = {
        "unit": unit_data.unit_name,
        "questions": questions ,
        "content": unit_data.content,
        "assessment": unit_data.assessment,
    }
    
    # Run the agent tasks
    result = question_crew.run(unit_data)
    
    # Save the results to the database
    save_results_to_db(unit_id, unit_name, question_crew.results)