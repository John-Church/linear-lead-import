import streamlit as st
import pandas as pd
import requests
import json

st.title("🎈 CSV to Linear Issue Importer")

# Function to create or update issues in Linear
def create_or_update_linear_issues(df, api_key):
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    url = "https://api.linear.app/graphql"

    st.write("Starting the import process...")

    # Initialize statistics
    stats = {
        "companies_processed": 0,
        "companies_created": 0,
        "companies_existing": 0,
        "individuals_processed": 0,
        "individuals_created": 0,
        "individuals_existing": 0
    }

    # Get the team ID
    with st.spinner("Fetching team information..."):
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
        response_data = response.json()
        if "errors" in response_data:
            st.error(f"Error fetching team information: {response_data['errors']}")
            return
        team_id = response_data["data"]["teams"]["nodes"][0]["id"]

    total_companies = len(df['Company Name'].unique())
    st.write(f"Found {total_companies} unique companies in the CSV.")

    # Create a progress bar for companies
    company_progress = st.progress(0)

    for index, (company, group) in enumerate(df.groupby('Company Name'), 1):
        # Update company progress bar
        company_progress.progress(index / total_companies)

        stats["companies_processed"] += 1

        # Check if company issue already exists
        company_search_query = """
        query($teamId: ID!, $title: String!) {
            issues(
                filter: {team: {id: {eq: $teamId}}, title: {eq: $title}}
                first: 1
            ) {
                nodes {
                    id
                    title
                }
            }
        }
        """
        variables = {
            "teamId": team_id,
            "title": company
        }
        response = requests.post(url, json={"query": company_search_query, "variables": variables}, headers=headers)
        response_data = response.json()
        if "errors" in response_data:
            st.error(f"Error searching for company issue: {response_data['errors']}")
            continue
        existing_company_issues = response_data["data"]["issues"]["nodes"]

        if existing_company_issues:
            company_issue_id = existing_company_issues[0]["id"]
            stats["companies_existing"] += 1
        else:
            # Create new company issue
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
            response_data = response.json()
            if "errors" in response_data:
                st.error(f"Error creating company issue: {response_data['errors']}")
                continue
            result = response_data["data"]["issueCreate"]
            if result["success"]:
                company_issue_id = result["issue"]["id"]
                stats["companies_created"] += 1
            else:
                st.error(f"Failed to create issue for {company}")
                continue

        # Create sub-issues for each individual
        total_individuals = len(group)
        
        # Create a progress bar for individuals within this company
        individual_progress = st.progress(0)

        for idx, (_, row) in enumerate(group.iterrows(), 1):
            # Update individual progress bar
            individual_progress.progress(idx / total_individuals)

            stats["individuals_processed"] += 1

            individual_title = f"{row['First Name']} {row['Last Name']} - {row['Prospect Job Title']}"
            
            # Check if individual issue already exists
            individual_search_query = """
            query($teamId: ID!, $title: String!, $parentId: ID!) {
                issues(
                    filter: {team: {id: {eq: $teamId}}, title: {eq: $title}, parent: {id: {eq: $parentId}}}
                    first: 1
                ) {
                    nodes {
                        id
                        title
                    }
                }
            }
            """
            variables = {
                "teamId": team_id,
                "title": individual_title,
                "parentId": company_issue_id
            }
            response = requests.post(url, json={"query": individual_search_query, "variables": variables}, headers=headers)
            response_data = response.json()
            if "errors" in response_data:
                st.error(f"Error searching for individual issue: {response_data['errors']}")
                continue
            existing_individual_issues = response_data["data"]["issues"]["nodes"]

            if existing_individual_issues:
                stats["individuals_existing"] += 1
            else:
                # Create new individual issue
                individual_mutation = """
                mutation($title: String!, $description: String!, $teamId: String!, $parentId: String!) {
                    issueCreate(input: {title: $title, description: $description, teamId: $teamId, parentId: $parentId}) {
                        success
                    }
                }
                """
                variables = {
                    "title": individual_title,
                    "description": format_individual_description(row),
                    "teamId": team_id,
                    "parentId": company_issue_id
                }
                response = requests.post(url, json={"query": individual_mutation, "variables": variables}, headers=headers)
                response_data = response.json()
                if "errors" in response_data:
                    st.error(f"Error creating individual issue: {response_data['errors']}")
                elif response_data["data"]["issueCreate"]["success"]:
                    stats["individuals_created"] += 1
                else:
                    st.error(f"Failed to create issue for {individual_title}")

        # Clear the individual progress bar after processing all individuals for this company
        individual_progress.empty()

    # Clear the company progress bar after processing all companies
    company_progress.empty()

    st.success("All issues created or updated successfully in Linear!")

    # Display statistics in a table
    st.write("Import Statistics:")
    stats_df = pd.DataFrame({
        "Category": ["Companies", "Companies", "Companies", "Individuals", "Individuals", "Individuals"],
        "Action": ["Processed", "Created", "Already Existing", "Processed", "Created", "Already Existing"],
        "Count": [
            stats['companies_processed'],
            stats['companies_created'],
            stats['companies_existing'],
            stats['individuals_processed'],
            stats['individuals_created'],
            stats['individuals_existing']
        ]
    })
    st.table(stats_df)

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
    st.write("CSV file loaded successfully. Here's a preview:")
    st.write(df.head())
    st.write(f"Total rows in CSV: {len(df)}")

    # Linear API Key input
    api_key = st.text_input("Enter your Linear API Key", type="password")

    if st.button("Import to Linear"):
        if api_key:
            with st.spinner("Importing data to Linear..."):
                create_or_update_linear_issues(df, api_key)
        else:
            st.error("Please enter your Linear API Key")

st.write(
    "This app imports leads from a CSV file into Linear, creating or updating company issues with individual sub-issues."
)
