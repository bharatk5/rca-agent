import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Service: {data['status']}")
            print(f"Total tickets: {data['knowledge_base']['total_tickets']}")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
    print()

def test_add_ticket():
    """Test adding tickets via API"""
    print("📝 Testing ticket addition...")
    
    test_tickets = [
        {
            "key": "API-001",
            "summary": "API endpoint returning 500 errors",
            "description": "The /api/users endpoint is returning 500 errors intermittently",
            "issue_type": "Bug",
            "priority": "High",
            "status": "Open",
            "assignee": "Backend Team",
            "reporter": "QA Team"
        },
        {
            "summary": "Add pagination to search results",
            "description": "Search results should be paginated to improve performance",
            "issue_type": "Story",
            "priority": "Medium",
            "status": "To Do",
            "assignee": "Frontend Team"
        }
    ]
    
    for i, ticket in enumerate(test_tickets):
        try:
            response = requests.post(
                f"{BASE_URL}/api/tickets",
                json=ticket,
                timeout=10
            )
            print(f"Ticket {i+1}: Status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Added: {data['ticket_id']}")
            else:
                print(f"  ❌ Error: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Connection error: {e}")
    print()

def test_search():
    """Test search functionality"""
    print("🔍 Testing search endpoints...")
    
    search_queries = [
        {"query": "API errors", "limit": 3},
        {"query": "authentication problems", "limit": 5},
        {"query": "database timeout", "limit": 2}
    ]
    
    for query in search_queries:
        print(f"Searching: '{query['query']}'")
        try:
            # Test POST method
            response = requests.post(
                f"{BASE_URL}/api/search",
                json=query,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  Found {data['total_found']} tickets")
                for ticket in data['tickets'][:2]:  # Show first 2 results
                    print(f"    • {ticket['ticket_id']}: {ticket['summary'][:50]}...")
            else:
                print(f"  ❌ Error: {response.text}")
            
            # Test GET method
            response = requests.get(
                f"{BASE_URL}/api/search",
                params={"q": query["query"], "limit": query["limit"]},
                timeout=10
            )
            print(f"  GET method: Status {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Connection error: {e}")
        print()

def test_filter():
    """Test filtering functionality"""
    print("🎯 Testing filter endpoint...")
    
    filter_tests = [
        {"issue_type": "Bug", "priority": "High"},
        {"status": "Open"},
        {"issue_type": "Story", "priority": "Medium"},
        {"assignee": "Backend Team"}
    ]
    
    for filters in filter_tests:
        filter_desc = ", ".join([f"{k}={v}" for k, v in filters.items()])
        print(f"Filtering by: {filter_desc}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/filter",
                json=filters,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Found {data['total_found']} matching tickets")
            else:
                print(f"  ❌ Error: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Connection error: {e}")
        print()

def test_stats():
    """Test statistics endpoint"""
    print("📊 Testing statistics endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/stats", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Statistics retrieved successfully")
            stats = data['statistics']
            print(f"  Total tickets: {stats.get('total_tickets', 0)}")
            
            if 'issue_types' in stats:
                print("  Issue types:")
                for issue_type, count in stats['issue_types'].items():
                    print(f"    • {issue_type}: {count}")
        else:
            print(f"❌ Error: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
    print()

def test_chat():
    """Test chat interface"""
    print("💬 Testing chat endpoint...")
    
    chat_messages = [
        "Find all authentication issues",
        "Show me high priority bugs",
        "Give me statistics about our tickets",
        "Add this ticket: {\"summary\": \"Chat API test ticket\", \"issue_type\": \"Task\", \"priority\": \"Low\"}"
    ]
    
    for message in chat_messages:
        print(f"Message: {message[:50]}...")
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/chat",
                json={"message": message, "session_id": "test-session"},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                response_text = data['response'][:100] + "..." if len(data['response']) > 100 else data['response']
                print(f"  ✅ Response: {response_text}")
            else:
                print(f"  ❌ Error: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Connection error: {e}")
        print()

def test_get_ticket():
    """Test getting specific ticket"""
    print("🎫 Testing get specific ticket...")
    
    # First, get a ticket ID from search
    try:
        response = requests.get(
            f"{BASE_URL}/api/search",
            params={"q": "bug", "limit": 1},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['tickets']:
                ticket_id = data['tickets'][0]['ticket_id']
                print(f"Testing with ticket: {ticket_id}")
                
                # Get specific ticket
                response = requests.get(f"{BASE_URL}/api/tickets/{ticket_id}", timeout=10)
                
                if response.status_code == 200:
                    ticket_data = response.json()
                    print(f"  ✅ Retrieved ticket: {ticket_data['ticket']['ticket_id']}")
                else:
                    print(f"  ❌ Error: {response.text}")
            else:
                print("  No tickets found to test with")
        else:
            print(f"❌ Search failed: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
    print()

def performance_test():
    """Basic performance testing"""
    print("⚡ Running performance tests...")
    
    # Test concurrent requests
    import concurrent.futures
    import threading
    
    def search_request():
        try:
            start_time = time.time()
            response = requests.get(
                f"{BASE_URL}/api/search",
                params={"q": "test", "limit": 5},
                timeout=10
            )
            end_time = time.time()
            return {
                'status': response.status_code, 
                'time': end_time - start_time,
                'success': response.status_code == 200
            }
        except:
            return {'status': 0, 'time': 10, 'success': False}
    
    # Run 5 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(search_request) for _ in range(5)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    successful = sum(1 for r in results if r['success'])
    avg_time = sum(r['time'] for r in results) / len(results)
    
    print(f"  Concurrent requests: {successful}/5 successful")
    print(f"  Average response time: {avg_time:.2f}s")
    print()

def main():
    """Run all tests"""
    print("🧪 Starting comprehensive API tests...")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)
    
    # Wait for server to be ready
    print("Waiting for server to be ready...")
    for i in range(30):  # Wait up to 30 seconds
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print("✅ Server is ready!")
                break
        except:
            pass
        time.sleep(1)
        if i % 5 == 0:
            print(f"Still waiting... ({i}/30)")
    else:
        print("❌ Server not responding, continuing with tests anyway...")
    
    print()
    
    # Run all tests
    test_health()
    test_add_ticket()
    test_search()
    test_filter()
    test_stats()
    test_chat()
    test_get_ticket()
    performance_test()
    
    print("✅ All tests completed!")
    print("\n🎉 API testing finished!")
    print(f"Visit {BASE_URL}/docs for interactive API documentation")

if __name__ == "__main__":
    main()
