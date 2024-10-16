import streamlit as st
import pandas as pd
import requests
import json

st.title("🎈 CSV to Linear Project/Issue Importer")

def detect_csv_format(df):
    """Detect the format of the CSV based on column names."""
    if all(col in df.columns for col in ['Company Name', 'First Name', 'Last Name', 'Prospect Job Title']):
        return 'original'
    elif all(col in df.columns for col in ['Company name', 'First name', 'Last name', 'Job title']):
        return 'export_contacts'
    else:
        return 'unknown'

def standardize_csv_data(df, csv_format):
    """Standardize CSV data into a consistent format."""
    standardized_data = []
    
    if csv_format == 'original':
        for _, row in df.iterrows():
            standardized_data.append({
                'company': {
                    'name': row['Company Name'],
                    'domain': row['Company Domain Name'],
                    'linkedin': row['Company Linkedin Page'],
                    'revenue': row['Company Revenue'],
                    'year_founded': row['Company Year Founded'],
                    'summary': row['Company Telescope Summary'],
                    'tags': row['Company Telescope Tags'],
                },
                'individual': {
                    'first_name': row['First Name'],
                    'last_name': row['Last Name'],
                    'job_title': row['Prospect Job Title'],
                    'email': row['Email'],
                    'phone': row['Phone Numbers'],
                    'linkedin': row['Linkedin Profile'],
                    'location': f"{row['City']}, {row['State']}, {row['Country']}",
                }
            })
    elif csv_format == 'export_contacts':
        for _, row in df.iterrows():
            standardized_data.append({
                'company': {
                    'name': row['Company name'],
                    'domain': row['Company domain'],
                    'website': row['Company website'],
                    'description': row['Company description'],
                    'year_founded': row['Company year founded'],
                    'employees': row['Company number of employees'],
                    'revenue': row['Company revenue'],
                    'linkedin': row['Company Linkedin URL'],
                    'industry': row['Company industry'],
                    'specialities': row['Company specialities'],
                },
                'individual': {
                    'first_name': row['First name'],
                    'last_name': row['Last name'],
                    'job_title': row['Job title'],
                    'work_email': row['Work email'],
                    'direct_email': row['Direct email'],
                    'phone1': row['Phone 1'],
                    'phone2': row['Phone 2'],
                    'linkedin': row['Linkedin URL'],
                    'location': f"{row['Company city']}, {row['Company state']}, {row['Company country']}",
                    'seniority': row['Seniority'],
                    'departments': row['Departments'],
                }
            })
    
    return standardized_data

def format_company_description(company):
    summary = f"Company: {company['name']}\n"
    summary += f"Domain: {company.get('domain', 'N/A')}\n"
    summary += f"Industry: {company.get('industry', 'N/A')}"
    return summary

def format_company_full_description(company):
    return "\n".join([f"{key.replace('_', ' ').title()}: {value}" for key, value in company.items() if value])

def format_individual_description(individual):
    return "\n".join([f"{key.replace('_', ' ').title()}: {value}" for key, value in individual.items() if value])

def create_or_update_linear_projects_and_issues(standardized_data, api_key):
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    url = "https://api.linear.app/graphql"

    st.write("Starting the import process...")

    # Initialize statistics
    stats = {
        "projects_processed": 0,
        "projects_created": 0,
        "projects_existing": 0,
        "issues_processed": 0,
        "issues_created": 0,
        "issues_existing": 0
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

    # Get or create "New Contact" label
    label_query = """
    query($teamId: String!) {
        issueLabels(filter: {team: {id: {eq: $teamId}}, name: {eq: "New Contact"}}) {
            nodes {
                id
                name
            }
        }
    }
    """
    label_variables = {
        "teamId": team_id
    }
    label_response = requests.post(url, json={"query": label_query, "variables": label_variables}, headers=headers)
    label_data = label_response.json()
    if label_data["data"]["issueLabels"]["nodes"]:
        new_contact_label_id = label_data["data"]["issueLabels"]["nodes"][0]["id"]
    else:
        # Create "New Contact" label if it doesn't exist
        create_label_mutation = """
        mutation($name: String!, $teamId: String!) {
            issueLabelCreate(input: {name: $name, teamId: $teamId}) {
                success
                issueLabel {
                    id
                }
            }
        }
        """
        create_label_variables = {
            "name": "New Contact",
            "teamId": team_id
        }
        create_label_response = requests.post(url, json={"query": create_label_mutation, "variables": create_label_variables}, headers=headers)
        create_label_data = create_label_response.json()
        if create_label_data["data"]["issueLabelCreate"]["success"]:
            new_contact_label_id = create_label_data["data"]["issueLabelCreate"]["issueLabel"]["id"]
        else:
            st.error("Failed to create 'New Contact' label")
            return

    total_companies = len(set(item['company']['name'] for item in standardized_data))
    st.write(f"Found {total_companies} unique companies in the CSV.")

    # Create a progress bar for companies
    company_progress = st.progress(0)

    processed_companies = set()

    for index, item in enumerate(standardized_data, 1):
        company = item['company']
        individual = item['individual']

        if company['name'] not in processed_companies:
            # Update company progress bar
            company_progress.progress(len(processed_companies) / total_companies)

            stats["projects_processed"] += 1
            processed_companies.add(company['name'])

            # Check if project already exists
            project_search_query = """
            query($name: String!) {
                projects(filter: {name: {eqIgnoreCase: $name}}, first: 1) {
                    nodes {
                        id
                        name
                    }
                }
            }
            """
            variables = {
                "name": company['name']
            }
            response = requests.post(url, json={"query": project_search_query, "variables": variables}, headers=headers)
            response_data = response.json()
            if "errors" in response_data:
                st.error(f"Error searching for project: {response_data['errors']}")
                continue
            existing_projects = response_data["data"]["projects"]["nodes"]

            if existing_projects:
                project_id = existing_projects[0]["id"]
                stats["projects_existing"] += 1
            else:
                # Create new project with truncated description
                short_description = format_company_description(company)[:255]
                project_mutation = """
                mutation($name: String!, $description: String!, $teamId: String!) {
                    projectCreate(input: {name: $name, description: $description, teamIds: [$teamId]}) {
                        success
                        project {
                            id
                        }
                    }
                }
                """
                variables = {
                    "name": company['name'],
                    "description": short_description,
                    "teamId": str(team_id)  # Convert to string
                }
                response = requests.post(url, json={"query": project_mutation, "variables": variables}, headers=headers)
                response_data = response.json()
                if "errors" in response_data:
                    st.error(f"Error creating project: {response_data['errors']}")
                    continue
                result = response_data["data"]["projectCreate"]
                if result["success"]:
                    project_id = result["project"]["id"]
                    stats["projects_created"] += 1

                    # Create a document with full description
                    full_description = format_company_full_description(company)
                    document_mutation = """
                    mutation($title: String!, $content: String!, $projectId: String!) {
                        documentCreate(input: {title: $title, content: $content, projectId: $projectId}) {
                            success
                            document {
                                id
                            }
                        }
                    }
                    """
                    document_variables = {
                        "title": f"{company['name']} - Full Description",
                        "content": full_description,
                        "projectId": str(project_id)  # Convert to string
                    }
                    document_response = requests.post(url, json={"query": document_mutation, "variables": document_variables}, headers=headers)
                    document_data = document_response.json()
                    if "errors" in document_data:
                        st.error(f"Error creating document for project: {document_data['errors']}")
                else:
                    st.error(f"Failed to create project for {company['name']}")
                    continue

        # Process individual as an issue
        stats["issues_processed"] += 1

        issue_title = f"{individual['first_name']} {individual['last_name']} - {individual['job_title']}"
        
        # Check if issue already exists
        issue_search_query = """
        query($teamId: ID!, $title: String!, $projectId: ID!) {
            issues(filter: {team: {id: {eq: $teamId}}, title: {eqIgnoreCase: $title}, project: {id: {eq: $projectId}}}, first: 1) {
                nodes {
                    id
                    title
                }
            }
        }
        """
        variables = {
            "teamId": team_id,
            "title": issue_title,
            "projectId": project_id
        }
        response = requests.post(url, json={"query": issue_search_query, "variables": variables}, headers=headers)
        response_data = response.json()
        if "errors" in response_data:
            st.error(f"Error searching for issue: {response_data['errors']}")
            continue
        existing_issues = response_data["data"]["issues"]["nodes"]

        if existing_issues:
            stats["issues_existing"] += 1
        else:
            # Create new issue with "New Contact" label
            issue_mutation = """
            mutation($title: String!, $description: String!, $teamId: String!, $projectId: String!, $labelIds: [String!]) {
                issueCreate(input: {title: $title, description: $description, teamId: $teamId, projectId: $projectId, labelIds: $labelIds}) {
                    success
                    issue {
                        id
                    }
                }
            }
            """
            variables = {
                "title": issue_title,
                "description": format_individual_description(individual),
                "teamId": str(team_id),
                "projectId": str(project_id),
                "labelIds": [str(new_contact_label_id)]
            }
            response = requests.post(url, json={"query": issue_mutation, "variables": variables}, headers=headers)
            response_data = response.json()
            if "errors" in response_data:
                st.error(f"Error creating issue: {response_data['errors']}")
            elif response_data["data"]["issueCreate"]["success"]:
                stats["issues_created"] += 1
            else:
                st.error(f"Failed to create issue for {issue_title}")

    # Clear the company progress bar after processing all companies
    company_progress.empty()

    st.success("All projects and issues created or updated successfully in Linear!")

    # Display statistics in a table
    st.write("Import Statistics:")
    stats_df = pd.DataFrame({
        "Category": ["Projects", "Projects", "Projects", "Issues", "Issues", "Issues"],
        "Action": ["Processed", "Created", "Already Existing", "Processed", "Created", "Already Existing"],
        "Count": [
            stats['projects_processed'],
            stats['projects_created'],
            stats['projects_existing'],
            stats['issues_processed'],
            stats['issues_created'],
            stats['issues_existing']
        ]
    })
    st.table(stats_df)

# File uploader
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    csv_format = detect_csv_format(df)
    
    if csv_format == 'unknown':
        st.error("Unknown CSV format. Please use a supported format.")
    else:
        st.write(f"Detected CSV format: {csv_format}")
        standardized_data = standardize_csv_data(df, csv_format)
        st.write("CSV file loaded and standardized successfully. Here's a preview:")
        st.write(pd.DataFrame(standardized_data[:5]))
        st.write(f"Total rows in CSV: {len(standardized_data)}")

        # Linear API Key input
        api_key = st.text_input("Enter your Linear API Key", type="password")

        if st.button("Import to Linear"):
            if api_key:
                with st.spinner("Importing data to Linear..."):
                    create_or_update_linear_projects_and_issues(standardized_data, api_key)
            else:
                st.error("Please enter your Linear API Key")

st.write(
    "This app imports leads from a CSV file into Linear, creating or updating projects for companies and issues for individuals."
)
