import streamlit as st
import PyPDF2
import requests
import json
from pptx import Presentation
from docx2pdf import convert
import tempfile
import os

# Initialize session state
if 'pdf_text' not in st.session_state:
    st.session_state.pdf_text = ""
if 'quiz' not in st.session_state:
    st.session_state.quiz = None
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}
if 'custom_prompt' not in st.session_state:
    st.session_state.custom_prompt = ""
if 'summary' not in st.session_state:
    st.session_state.summary = ""

def convert_to_pdf(file):
    file_extension = os.path.splitext(file.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
        temp_file.write(file.getvalue())
        temp_file_path = temp_file.name

    pdf_path = temp_file_path + ".pdf"

    if file_extension == ".pptx":
        prs = Presentation(temp_file_path)
        prs.save(pdf_path)
    elif file_extension == ".docx":
        convert(temp_file_path, pdf_path)
    else:
        os.rename(temp_file_path, pdf_path)

    return pdf_path

def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def query_ollama(context, task):
    url = "http://localhost:11434/api/generate"
    data = {
        "model": "llama3.1",
        "prompt": f"Context: {context}\n\nTask: {task}\n\nResponse:",
        "stream": False
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return json.loads(response.text)["response"]
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection Error: {str(e)}")
        return None

def generate_quiz(context, num_questions=5):
    task = f"""Generate a quiz with {num_questions} multiple-choice questions based on the given context: "{context}". 
    For each question, provide 4 options (A, B, C, D) and indicate the correct answer.
    Ensure the questions are relevant to the topic: {context}. Also if the questions is for learning a language or grammar 
    like 'take a quiz on present tense' or any other tense I expect you to prepare questions and options like this
    Do not include meta-level questions like 'What is the purpose of this quiz?'
    Format the output as a JSON string with the following structure:
    {{
        "questions": [
            {{
                "question": "Question text here",
                "options": {{
                    "A": "Option A text",
                    "B": "Option B text",
                    "C": "Option C text",
                    "D": "Option D text"
                }},
                "correct_answer": "Correct option letter"
            }},
            ...
        ]
    }}
    """
    
    with st.spinner("Generating quiz..."):
        response = query_ollama(context, task)
    
    if response:
        try:
            quiz = json.loads(response)
            return quiz
        except json.JSONDecodeError:
            st.error("Failed to decode quiz response. The response is not in valid JSON format.")
            return None
    else:
        st.error("Failed to generate a valid quiz. Please check your network or try again.")
        return None

def summarize_content(context):
    task = f"""Summarize the following content: "{context}". 
    Provide a concise summary that captures the main points and key information.
    """
    
    with st.spinner("Summarizing content..."):
        response = query_ollama(context, task)
    
    if response:
        return response
    else:
        st.error("Failed to generate a summary. Please check your network or try again.")
        return None

st.set_page_config(page_title="PDF Assistant", layout="wide")

st.title("PDF Assistant for Students and Researchers")

uploaded_file = st.file_uploader("Upload your file", type=["pdf", "docx", "pptx"])

if uploaded_file is not None:
    if st.button("Process File"):
        with st.spinner("Processing your file..."):
            if uploaded_file.type == "application/pdf":
                pdf_file = uploaded_file
            else:
                pdf_path = convert_to_pdf(uploaded_file)
                pdf_file = open(pdf_path, "rb")

            st.session_state.pdf_text = extract_text_from_pdf(pdf_file)
            st.success("File uploaded and processed successfully!")

# New text area to allow user to input a custom prompt
st.subheader("Or input your own custom prompt")
st.session_state.custom_prompt = st.text_area("Enter your prompt (optional)", "")

# Input for number of questions
num_questions = st.number_input("Number of quiz questions", min_value=1, value=5)

if st.session_state.pdf_text or st.session_state.custom_prompt:
    st.subheader("Generate Content")
    
    # User can choose to generate a quiz or summarize the content
    content_type = st.radio("Select content type to generate:", ("Quiz", "Summary"))
    
    if st.button("Generate"):
        context = st.session_state.custom_prompt or st.session_state.pdf_text
        if content_type == "Quiz":
            st.session_state.quiz = generate_quiz(context, num_questions)
            st.session_state.user_answers = {}
        elif content_type == "Summary":
            st.session_state.summary = summarize_content(context)

    if st.session_state.quiz:
        for i, q in enumerate(st.session_state.quiz["questions"]):
            st.write(f"**Question {i+1}:** {q['question']}")
            answer = st.radio(f"Select your answer for question {i+1}:", 
                              options=list(q['options'].keys()),
                              format_func=lambda x: f"{x}: {q['options'][x]}",
                              key=f"q{i}")
            st.session_state.user_answers[i] = answer

        if st.button("Check Answers"):
            score = 0
            for i, q in enumerate(st.session_state.quiz["questions"]):
                user_answer = st.session_state.user_answers.get(i)
                correct_answer = q['correct_answer']
                if user_answer == correct_answer:
                    st.success(f"Question {i+1}: Correct!")
                    score += 1
                else:
                    st.error(f"Question {i+1}: Incorrect. The correct answer is {correct_answer}: {q['options'][correct_answer]}")
            st.write(f"Your score: {score}/{len(st.session_state.quiz['questions'])}")

    if st.session_state.summary:
        st.subheader("Summary")
        st.write(st.session_state.summary)

st.sidebar.title("About")
st.sidebar.info(
    "This app allows you to upload PDF, Word, or PowerPoint files and generate an interactive quiz or summary based on the content. "
    "It also allows you to input custom prompts for content generation."
)

st.sidebar.title("Instructions")
st.sidebar.markdown(
    """
    1. Upload a file (PDF, Word, or PowerPoint)
    2. Alternatively, enter a custom prompt in the text area
    3. Specify the number of quiz questions (if generating a quiz)
    4. Select the content type to generate (Quiz or Summary)
    5. Click 'Generate' to create the selected content
    6. If generating a quiz, answer the questions by selecting the appropriate options
    7. Click 'Check Answers' to see your score and correct answers (if generating a quiz)
    """
)