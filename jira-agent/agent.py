# jira_agent/agent.py - Modern Google ADK 1.8.0 JIRA Agent with ChromaDB
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Modern Google ADK imports (v1.8.0)
from google.adk.agents import Agent

# ChromaDB imports
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# Google Cloud imports
from google.cloud import storage, firestore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JIRAKnowledgeBase:
    """ChromaDB-powered knowledge base for JIRA tickets - optimized for ADK 1.8.0"""
    
    def __init__(self, persist_directory: str = "./chromadb_data"):
        """Initialize ChromaDB with modern configuration"""
        # Ensure directory exists
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                allow_reset=True,
                anonymized_telemetry=False,
                chroma_db_impl="duckdb+parquet",
                persist_directory=persist_directory
            )
        )
        
        # Use optimized embedding function
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
            normalize_embeddings=True
        )
        
        # Initialize or get collection
        try:
            self.collection = self.client.get_collection(
                name="jira_tickets",
                embedding_function=self.embedding_function
            )
            logger.info("Connected to existing JIRA tickets collection")
        except ValueError:
            self.collection = self.client.create_collection(
                name="jira_tickets",
                embedding_function=self.embedding_function,
                metadata={"description": "JIRA tickets knowledge base", "version": "1.0"}
            )
            logger.info("Created new JIRA tickets collection")
    
    def add_ticket(self, ticket_data: Dict[str, Any]) -> str:
        """Add JIRA ticket to knowledge base"""
        ticket_id = ticket_data.get('key', f"TICKET-{str(uuid.uuid4())[:8]}")
        
        # Create searchable document
        document = self._create_searchable_document(ticket_data)
        metadata = self._extract_metadata(ticket_data)
        
        try:
            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[ticket_id]
            )
            logger.info(f"Added ticket {ticket_id} to knowledge base")
            return ticket_id
        except Exception as e:
            logger.error(f"Failed to add ticket {ticket_id}: {str(e)}")
            raise
    
    def search_tickets(self, query: str, n_results: int = 5, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Search tickets using semantic similarity"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, 20),  # Limit for performance
                where=filters or {}
            )
            
            formatted_results = []
            for i, doc_id in enumerate(results['ids'][0]):
                result = {
                    'ticket_id': doc_id,
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'relevance_score': round(1 - results['distances'][0][i], 3)
                }
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        try:
            count = self.collection.count()
            
            # Get sample for analysis
            sample = self.collection.get(limit=min(50, count))
            
            stats = {'total_tickets': count}
            
            if sample['metadatas']:
                # Analyze metadata
                issue_types = {}
                priorities = {}
                statuses = {}
                
                for metadata in sample['metadatas']:
                    issue_type = metadata.get('issue_type', 'Unknown')
                    priority = metadata.get('priority', 'Unknown')
                    status = metadata.get('status', 'Unknown')
                    
                    issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
                    priorities[priority] = priorities.get(priority, 0) + 1
                    statuses[status] = statuses.get(status, 0) + 1
                
                stats.update({
                    'sample_size': len(sample['metadatas']),
                    'issue_types': issue_types,
                    'priorities': priorities,
                    'statuses': statuses
                })
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {'total_tickets': 0, 'error': str(e)}
    
    def _create_searchable_document(self, ticket_data: Dict[str, Any]) -> str:
        """Convert ticket to searchable document - optimized for embeddings"""
        key = ticket_data.get('key', '')
        summary = ticket_data.get('summary', '')
        description = ticket_data.get('description', '')
        issue_type = ticket_data.get('issuetype', {}).get('name', '') if isinstance(ticket_data.get('issuetype'), dict) else ticket_data.get('issue_type', '')
        status = ticket_data.get('status', {}).get('name', '') if isinstance(ticket_data.get('status'), dict) else ticket_data.get('status', '')
        priority = ticket_data.get('priority', {}).get('name', '') if isinstance(ticket_data.get('priority'), dict) else ticket_data.get('priority', '')
        
        # Create structured document for better embeddings
        document = f"""Ticket: {key}
Type: {issue_type}
Priority: {priority}
Status: {status}
Summary: {summary}
Description: {description}"""
        
        return document.strip()
    
    def _extract_metadata(self, ticket_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract metadata for filtering and display"""
        # Handle both JIRA API format and simplified format
        def safe_extract(data, key, subkey=None):
            value = data.get(key, {})
            if isinstance(value, dict) and subkey:
                return value.get(subkey, '')
            elif isinstance(value, str):
                return value
            return str(value) if value else ''
        
        metadata = {
            'key': ticket_data.get('key', ''),
            'issue_type': safe_extract(ticket_data, 'issuetype', 'name') or ticket_data.get('issue_type', ''),
            'priority': safe_extract(ticket_data, 'priority', 'name') or ticket_data.get('priority', ''),
            'status': safe_extract(ticket_data, 'status', 'name') or ticket_data.get('status', ''),
            'assignee': safe_extract(ticket_data, 'assignee', 'displayName') or ticket_data.get('assignee', ''),
            'reporter': safe_extract(ticket_data, 'reporter', 'displayName') or ticket_data.get('reporter', ''),
            'project': safe_extract(ticket_data, 'project', 'key') or ticket_data.get('project', ''),
            'created': ticket_data.get('created', ''),
            'indexed_at': datetime.now().isoformat()
        }
        
        # Remove empty values to optimize storage
        return {k: v for k, v in metadata.items() if v}

# Initialize global knowledge base
knowledge_base = JIRAKnowledgeBase()

# ADK Tool Functions (following modern ADK 1.8.0 patterns)
def add_jira_ticket(ticket_json: str) -> dict:
    """Add a JIRA ticket to the knowledge base.
    
    Args:
        ticket_json (str): JSON string containing JIRA ticket data
        
    Returns:
        dict: Status and result information
    """
    try:
        ticket_data = json.loads(ticket_json)
        
        # Validate required fields
        if not ticket_data.get('key') and not ticket_data.get('summary'):
            return {
                "status": "error",
                "error_message": "Ticket must have either 'key' or 'summary' field"
            }
        
        ticket_id = knowledge_base.add_ticket(ticket_data)
        
        return {
            "status": "success",
            "result": f"Successfully added ticket {ticket_id} to knowledge base",
            "ticket_id": ticket_id
        }
        
    except json.JSONDecodeError:
        return {
            "status": "error",
            "error_message": "Invalid JSON format provided"
        }
    except Exception as e:
        return {
            "status": "error", 
            "error_message": f"Failed to add ticket: {str(e)}"
        }

def search_jira_tickets(query: str, limit: int = 5) -> dict:
    """Search JIRA tickets using semantic similarity.
    
    Args:
        query (str): Search query describing what to find
        limit (int): Maximum number of results to return (default: 5, max: 20)
        
    Returns:
        dict: Search results with ticket information
    """
    try:
        limit = min(max(1, limit), 20)  # Ensure reasonable limits
        results = knowledge_base.search_tickets(query, limit)
        
        if not results:
            return {
                "status": "success",
                "result": "No tickets found matching your query.",
                "total_found": 0,
                "tickets": []
            }
        
        # Format results for better readability
        formatted_tickets = []
        for result in results:
            ticket_info = {
                "ticket_id": result['ticket_id'],
                "relevance_score": result['relevance_score'],
                "summary": result['content'].split('\n')[0].replace('Ticket: ', ''),
                "type": result['metadata'].get('issue_type', 'Unknown'),
                "priority": result['metadata'].get('priority', 'Unknown'),
                "status": result['metadata'].get('status', 'Unknown'),
                "assignee": result['metadata'].get('assignee', 'Unassigned')
            }
            formatted_tickets.append(ticket_info)
        
        summary = f"Found {len(results)} relevant tickets:\n\n"
        for ticket in formatted_tickets:
            summary += f"🎫 **{ticket['ticket_id']}** (Relevance: {ticket['relevance_score']})\n"
            summary += f"   Type: {ticket['type']} | Priority: {ticket['priority']} | Status: {ticket['status']}\n"
            summary += f"   Assignee: {ticket['assignee']}\n"
            summary += f"   {ticket['summary']}\n\n"
        
        return {
            "status": "success",
            "result": summary,
            "total_found": len(results),
            "tickets": formatted_tickets
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Search failed: {str(e)}"
        }

def get_jira_statistics() -> dict:
    """Get statistics about the JIRA knowledge base.
    
    Returns:
        dict: Statistics about the knowledge base
    """
    try:
        stats = knowledge_base.get_stats()
        
        if 'error' in stats:
            return {
                "status": "error",
                "error_message": stats['error']
            }
        
        result = f"📊 **JIRA Knowledge Base Statistics**\n\n"
        result += f"Total Tickets: {stats['total_tickets']}\n"
        
        if stats['total_tickets'] > 0:
            result += f"Sample Size: {stats.get('sample_size', 0)}\n\n"
            
            if 'issue_types' in stats:
                result += "**Issue Types:**\n"
                for issue_type, count in stats['issue_types'].items():
                    result += f"  • {issue_type}: {count}\n"
                result += "\n"
            
            if 'priorities' in stats:
                result += "**Priorities:**\n"
                for priority, count in stats['priorities'].items():
                    result += f"  • {priority}: {count}\n"
                result += "\n"
            
            if 'statuses' in stats:
                result += "**Statuses:**\n"
                for status, count in stats['statuses'].items():
                    result += f"  • {status}: {count}\n"
        
        return {
            "status": "success",
            "result": result,
            "raw_stats": stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Failed to get statistics: {str(e)}"
        }

def filter_jira_tickets(issue_type: str = "", priority: str = "", status: str = "", assignee: str = "") -> dict:
    """Filter JIRA tickets by specific criteria.
    
    Args:
        issue_type (str): Filter by issue type (Bug, Story, Task, etc.)
        priority (str): Filter by priority (High, Medium, Low, etc.)
        status (str): Filter by status (Open, In Progress, Done, etc.)
        assignee (str): Filter by assignee name
        
    Returns:
        dict: Filtered ticket results
    """
    try:
        # Build filter criteria
        filters = {}
        if issue_type:
            filters['issue_type'] = issue_type
        if priority:
            filters['priority'] = priority
        if status:
            filters['status'] = status
        if assignee:
            filters['assignee'] = assignee
        
        if not filters:
            return {
                "status": "error",
                "error_message": "At least one filter criteria must be provided"
            }
        
        # Use search with empty query but with filters
        results = knowledge_base.search_tickets("", n_results=20, filters=filters)
        
        if not results:
            filter_desc = ", ".join([f"{k}={v}" for k, v in filters.items()])
            return {
                "status": "success",
                "result": f"No tickets found matching filters: {filter_desc}",
                "total_found": 0
            }
        
        filter_desc = ", ".join([f"{k}={v}" for k, v in filters.items()])
        result = f"Found {len(results)} tickets matching filters ({filter_desc}):\n\n"
        
        for ticket in results:
            result += f"🎫 **{ticket['ticket_id']}**\n"
            result += f"   Type: {ticket['metadata'].get('issue_type', 'Unknown')}\n"
            result += f"   Priority: {ticket['metadata'].get('priority', 'Unknown')}\n"
            result += f"   Status: {ticket['metadata'].get('status', 'Unknown')}\n"
            result += f"   Assignee: {ticket['metadata'].get('assignee', 'Unassigned')}\n\n"
        
        return {
            "status": "success",
            "result": result,
            "total_found": len(results)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Filter operation failed: {str(e)}"
        }

# Modern ADK 1.8.0 Agent Definition
root_agent = Agent(
    name="jira_knowledge_agent",
    model="gemini-2.0-flash-exp",  # Using latest Gemini model
    description=(
        "An intelligent JIRA knowledge base agent that can add, search, and analyze JIRA tickets "
        "using semantic search powered by ChromaDB. The agent helps teams find relevant tickets, "
        "track project statistics, and manage their JIRA knowledge base efficiently."
    ),
    instruction=(
        "You are an expert JIRA assistant with access to a comprehensive knowledge base of JIRA tickets. "
        "Your capabilities include:\n\n"
        "1. **Adding Tickets**: Help users add new JIRA tickets to the knowledge base\n"
        "2. **Searching**: Find relevant tickets using semantic search - you can understand context and find related issues even with different wording\n"
        "3. **Filtering**: Filter tickets by specific criteria like type, priority, status, or assignee\n"
        "4. **Analytics**: Provide statistics and insights about the ticket collection\n\n"
        "When users ask about tickets:\n"
        "- Use semantic search to find relevant tickets even if they use different words\n"
        "- Provide clear, formatted results with ticket IDs, relevance scores, and key details\n"
        "- Suggest related searches when appropriate\n"
        "- For complex queries, break them down into multiple searches if needed\n\n"
        "When adding tickets:\n"
        "- Guide users on the proper JSON format if needed\n"
        "- Validate that essential fields are present\n"
        "- Confirm successful additions with the ticket ID\n\n"
        "Always be helpful, accurate, and provide actionable insights based on the ticket data."
    ),
    tools=[
        add_jira_ticket,
        search_jira_tickets, 
        get_jira_statistics,
        filter_jira_tickets
    ],
)

# Sample data loading function
def load_sample_data():
    """Load sample JIRA tickets for demonstration"""
    sample_tickets = [
        {
            "key": "PROJ-101",
            "summary": "Login authentication failing intermittently",
            "description": "Users report random login failures with correct credentials. Happens about 20% of the time during peak hours.",
            "issue_type": "Bug",
            "priority": "High", 
            "status": "In Progress",
            "assignee": "John Developer",
            "reporter": "Sarah QA",
            "project": "PROJ",
            "created": "2024-01-15T10:30:00.000Z"
        },
        {
            "key": "PROJ-102",
            "summary": "Implement dark mode for mobile app",
            "description": "Add dark mode theme support for the mobile application to improve user experience and reduce eye strain.",
            "issue_type": "Story",
            "priority": "Medium",
            "status": "To Do", 
            "assignee": "Jane Designer",
            "reporter": "Product Manager",
            "project": "PROJ",
            "created": "2024-01-16T09:15:00.000Z"
        },
        {
            "key": "PROJ-103", 
            "summary": "Database connection timeout in production",
            "description": "Production database queries are timing out after 30 seconds. Affecting user dashboard load times.",
            "issue_type": "Bug",
            "priority": "Critical",
            "status": "Open",
            "assignee": "Database Team",
            "reporter": "Monitoring System", 
            "project": "PROJ",
            "created": "2024-01-17T14:22:00.000Z"
        },
        {
            "key": "PROJ-104",
            "summary": "Add unit tests for payment processing",
            "description": "Increase test coverage for payment processing module to ensure reliability.",
            "issue_type": "Task", 
            "priority": "Medium",
            "status": "In Progress",
            "assignee": "Test Team",
            "reporter": "Tech Lead",
            "project": "PROJ", 
            "created": "2024-01-18T11:45:00.000Z"
        }
    ]
    
    print("Loading sample JIRA tickets...")
    for ticket in sample_tickets:
        try:
            knowledge_base.add_ticket(ticket)
            print(f"✅ Added {ticket['key']}")
        except Exception as e:
            print(f"❌ Failed to add {ticket['key']}: {str(e)}")
    
    print(f"\n🎉 Sample data loaded! Knowledge base now contains {knowledge_base.collection.count()} tickets.")

if __name__ == "__main__":
    # Load sample data when running directly
    if knowledge_base.collection.count() == 0:
        load_sample_data()
    else:
        print(f"Knowledge base already contains {knowledge_base.collection.count()} tickets.")
    
    print("\n🤖 JIRA Knowledge Agent is ready!")
    print("You can now use 'adk web' to interact with the agent in the browser UI.")
    print("\nExample queries to try:")
    print("• 'Find all authentication issues'")
    print("• 'Show me high priority bugs'") 
    print("• 'What tickets are assigned to John?'")
    print("• 'Give me statistics about our tickets'")
    print("• 'Add a new ticket: {\"summary\": \"New feature request\", \"issue_type\": \"Story\"}'")