import streamlit as st
import pandas as pd
import requests
import json

st.title("🎈 CSV to Linear Issue Importer")

# Function to create issues in Linear
def create_linear_issues(df, api_key):
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    url = "https://api.linear.app/graphql"

    # Get the team ID
    query = """
    query {
        teams {
            nodes {
                id
                name
            }
        }
    }
    """
    response = requests.post(url, json={"query": query}, headers=headers)
    team_id = response.json()["data"]["teams"]["nodes"][0]["id"]

    for company, group in df.groupby('Company Name'):
        # Create main issue for the company
        company_mutation = """
        mutation($title: String!, $description: String!, $teamId: String!) {
            issueCreate(input: {title: $title, description: $description, teamId: $teamId}) {
                success
                issue {
                    id
                }
            }
        }
        """
        variables = {
            "title": company,
            "description": format_company_description(group.iloc[0]),
            "teamId": team_id
        }
        response = requests.post(url, json={"query": company_mutation, "variables": variables}, headers=headers)
        company_issue_id = response.json()["data"]["issueCreate"]["issue"]["id"]

        # Create sub-issues for each individual
        for _, row in group.iterrows():
            individual_mutation = """
            mutation($title: String!, $description: String!, $teamId: String!, $parentId: String!) {
                issueCreate(input: {title: $title, description: $description, teamId: $teamId, parentId: $parentId}) {
                    success
                }
            }
            """
            variables = {
                "title": f"{row['First Name']} {row['Last Name']} - {row['Prospect Job Title']}",
                "description": format_individual_description(row),
                "teamId": team_id,
                "parentId": company_issue_id
            }
            requests.post(url, json={"query": individual_mutation, "variables": variables}, headers=headers)

    st.success("Issues created successfully in Linear!")

# Function to format company description
def format_company_description(company_row):
    return f"""
Company: {company_row['Company Name']}
Domain: {company_row['Company Domain Name']}
LinkedIn: {company_row['Company Linkedin Page']}
Revenue: {company_row['Company Revenue']}
Year Founded: {company_row['Company Year Founded']}
Summary: {company_row['Company Telescope Summary']}
Tags: {company_row['Company Telescope Tags']}
    """

# Function to format individual description
def format_individual_description(row):
    return f"""
Name: {row['First Name']} {row['Last Name']}
Job Title: {row['Prospect Job Title']}
Email: {row['Email']}
Phone: {row['Phone Numbers']}
LinkedIn: {row['Linkedin Profile']}
Location: {row['City']}, {row['State']}, {row['Country']}
    """

# File uploader
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write(df)

    # Linear API Key input
    api_key = st.text_input("Enter your Linear API Key", type="password")

    if st.button("Import to Linear"):
        if api_key:
            create_linear_issues(df, api_key)
        else:
            st.error("Please enter your Linear API Key")

st.write(
    "This app imports leads from a CSV file into Linear, creating company issues with individual sub-issues."
)
