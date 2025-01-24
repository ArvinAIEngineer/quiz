import streamlit as st
import psycopg2
import os
from dotenv import load_dotenv
from llama_index.llms.groq import Groq
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# Groq LLM Configuration
api_key = os.getenv('GROQ_API_KEY')
llm = Groq(model="llama3-70b-8192", api_key=api_key)

# Database Connection Configuration
DB_USER = os.getenv('NEON_DB_USER')
DB_PASSWORD = os.getenv('NEON_DB_PASSWORD')
DB_HOST = os.getenv('NEON_DB_HOST')
DB_PORT = os.getenv('NEON_DB_PORT')
DB_NAME = os.getenv('NEON_DB_NAME')

def fetch_quizzes():
    """Fetch available quizzes from the database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM quizzes;")
        quizzes = cursor.fetchall()
        return quizzes
    except Exception as e:
        st.error(f"Error fetching quizzes: {e}")
        return []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def fetch_questions(quiz_id):
    """Fetch questions for a specific quiz."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, question, option_a, option_b, option_c, option_d FROM questions WHERE quiz_id = %s;",
            (quiz_id,)
        )
        questions = cursor.fetchall()
        return questions
    except Exception as e:
        st.error(f"Error fetching questions: {e}")
        return []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def log_quiz_results(quiz_id, candidate_name, answers, total_score):
    """Log quiz results to the database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO quiz_results (quiz_id, candidate_name, answers, total_score) VALUES (%s, %s, %s, %s);",
            (quiz_id, candidate_name, json.dumps(answers), total_score)
        )
        conn.commit()
        st.success("Quiz results logged successfully!")
    except Exception as e:
        st.error(f"Error logging quiz results: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_score_from_groq(question, selected_answer, rationale):
    """Get a score (out of 10) from Groq for the user's answer and rationale."""
    prompt = (
        f"Question: {question}\n"
        f"Selected Answer: {selected_answer}\n"
        f"Rationale: {rationale}\n\n"
        "Rate the user's answer and rationale on a scale of 0 to 10, where 10 is excellent. "
        "Provide only the numeric score (e.g., 8)."
    )
    response = llm.complete(prompt)
    try:
        return float(response.text.strip())
    except ValueError:
        st.error(f"Failed to parse score from Groq response: {response.text}")
        return 0

def main():
    st.title("Quiz App")

    # Initialize session state
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'selected_quiz' not in st.session_state:
        st.session_state.selected_quiz = None
    if 'questions' not in st.session_state:
        st.session_state.questions = []
    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0
    if 'answers' not in st.session_state:
        st.session_state.answers = []
    if 'quiz_completed' not in st.session_state:
        st.session_state.quiz_completed = False
    if 'total_score' not in st.session_state:
        st.session_state.total_score = 0
    if 'proceed_to_quiz' not in st.session_state:
        st.session_state.proceed_to_quiz = False

    # Step 1: Enter Username
    if not st.session_state.username:
        st.session_state.username = st.text_input("Enter your username:")
        if st.session_state.username:
            st.success(f"Welcome, {st.session_state.username}!")

    # Step 2: Select Quiz
    if st.session_state.username and not st.session_state.proceed_to_quiz:
        quizzes = fetch_quizzes()
        if quizzes:
            quiz_options = {quiz[1]: quiz[0] for quiz in quizzes}  # {title: id}
            selected_quiz_title = st.selectbox("Select a quiz:", list(quiz_options.keys()))
            st.session_state.selected_quiz = quiz_options[selected_quiz_title]

            # Proceed button
            if st.button("Proceed"):
                st.session_state.proceed_to_quiz = True
                st.session_state.questions = fetch_questions(st.session_state.selected_quiz)
        else:
            st.warning("No quizzes available.")

    # Step 3: Display Questions
    if st.session_state.proceed_to_quiz and st.session_state.questions and not st.session_state.quiz_completed:
        question_data = st.session_state.questions[st.session_state.current_question_index]
        question_id, question, option_a, option_b, option_c, option_d = question_data

        st.subheader(f"Question {st.session_state.current_question_index + 1}")
        st.write(question)

        # Display options
        selected_answer = st.radio(
            "Select your answer:",
            [option_a, option_b, option_c, option_d],
            key=f"question_{question_id}"
        )

        # Rationale input (mandatory)
        rationale = st.text_area("Explain your answer (mandatory):", key=f"rationale_{question_id}")

        # Navigation buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.current_question_index > 0:
                if st.button("Previous"):
                    st.session_state.current_question_index -= 1
                    st.rerun()
        with col2:
            if st.session_state.current_question_index < len(st.session_state.questions) - 1:
                if st.button("Next"):
                    if not rationale.strip():
                        st.warning("Please provide a rationale before proceeding.")
                    else:
                        # Log the answer and rationale
                        st.session_state.answers.append({
                            "question": question,
                            "selected_answer": selected_answer,
                            "rationale": rationale
                        })
                        st.session_state.current_question_index += 1
                        st.rerun()
            else:
                if st.button("Submit"):
                    if not rationale.strip():
                        st.warning("Please provide a rationale before submitting.")
                    else:
                        # Log the final answer and rationale
                        st.session_state.answers.append({
                            "question": question,
                            "selected_answer": selected_answer,
                            "rationale": rationale
                        })

                        # Calculate scores and log results
                        scores = []
                        for answer in st.session_state.answers:
                            score = get_score_from_groq(
                                answer["question"],
                                answer["selected_answer"],
                                answer["rationale"]
                            )
                            scores.append(score)

                        # Calculate average score
                        st.session_state.total_score = sum(scores) / len(scores)

                        # Log results to the database
                        log_quiz_results(
                            st.session_state.selected_quiz,
                            st.session_state.username,
                            st.session_state.answers,
                            st.session_state.total_score
                        )

                        # Mark quiz as completed
                        st.session_state.quiz_completed = True
                        st.rerun()

    # Step 4: End Screen
    if st.session_state.quiz_completed:
        st.success("Quiz completed! Thank you for participating.")
        st.write(f"Your average score is: **{st.session_state.total_score:.2f}/10**")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Retake Quiz"):
                # Reset session state for retaking the quiz
                st.session_state.current_question_index = 0
                st.session_state.answers = []
                st.session_state.quiz_completed = False
                st.session_state.total_score = 0
                st.session_state.proceed_to_quiz = False
                st.rerun()
        with col2:
            if st.button("Exit"):
                st.session_state.clear()
                st.rerun()

if __name__ == "__main__":
    main()
