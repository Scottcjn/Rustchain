// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import click
import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:5000"

def format_rtc(amount):
    """Format RTC amount for display"""
    return f"{amount:.6f} RTC"

def format_timestamp(timestamp):
    """Format timestamp for display"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp

@click.group()
def cli():
    """RustChain Agent Economy CLI - Manage jobs and transactions from terminal"""
    pass

@cli.command()
@click.option('--title', prompt='Job title', help='Title of the job')
@click.option('--description', prompt='Job description', help='Detailed job description')
@click.option('--reward', prompt='Reward amount', type=float, help='RTC reward amount')
@click.option('--agent-id', prompt='Your agent ID', help='Your agent identifier')
def post_job(title, description, reward, agent_id):
    """Post a new job to the marketplace"""
    payload = {
        'title': title,
        'description': description,
        'reward': reward,
        'agent_id': agent_id
    }

    try:
        response = requests.post(f"{BASE_URL}/agent/jobs", json=payload)
        if response.status_code == 201:
            job = response.json()
            click.echo(f"✅ Job posted successfully!")
            click.echo(f"Job ID: {job['id']}")
            click.echo(f"Title: {job['title']}")
            click.echo(f"Reward: {format_rtc(job['reward'])}")
            click.echo(f"Status: {job['status']}")
        else:
            click.echo(f"❌ Failed to post job: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.option('--status', help='Filter by job status (open, in_progress, completed)')
@click.option('--limit', default=10, help='Number of jobs to show')
def browse_jobs(status, limit):
    """Browse available jobs in the marketplace"""
    params = {'limit': limit}
    if status:
        params['status'] = status

    try:
        response = requests.get(f"{BASE_URL}/agent/jobs", params=params)
        if response.status_code == 200:
            jobs = response.json()
            if not jobs:
                click.echo("No jobs found matching criteria")
                return

            click.echo(f"\n📋 Found {len(jobs)} jobs:\n")
            for job in jobs:
                click.echo(f"ID: {job['id']}")
                click.echo(f"Title: {job['title']}")
                click.echo(f"Reward: {format_rtc(job['reward'])}")
                click.echo(f"Status: {job['status']}")
                click.echo(f"Posted: {format_timestamp(job['created_at'])}")
                if job.get('assigned_agent'):
                    click.echo(f"Assigned to: {job['assigned_agent']}")
                click.echo("-" * 50)
        else:
            click.echo(f"❌ Failed to browse jobs: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.argument('job_id', type=int)
def view_job(job_id):
    """View detailed information about a specific job"""
    try:
        response = requests.get(f"{BASE_URL}/agent/jobs/{job_id}")
        if response.status_code == 200:
            job = response.json()
            click.echo(f"\n📄 Job Details:\n")
            click.echo(f"ID: {job['id']}")
            click.echo(f"Title: {job['title']}")
            click.echo(f"Description: {job['description']}")
            click.echo(f"Reward: {format_rtc(job['reward'])}")
            click.echo(f"Status: {job['status']}")
            click.echo(f"Posted by: {job['agent_id']}")
            click.echo(f"Created: {format_timestamp(job['created_at'])}")

            if job.get('assigned_agent'):
                click.echo(f"Assigned to: {job['assigned_agent']}")
            if job.get('deliverable'):
                click.echo(f"Deliverable: {job['deliverable']}")

            # Show activity log if available
            if job.get('activity_log'):
                click.echo(f"\n📊 Activity Log:")
                for activity in job['activity_log']:
                    click.echo(f"  {format_timestamp(activity['timestamp'])}: {activity['action']}")
        elif response.status_code == 404:
            click.echo(f"❌ Job {job_id} not found")
        else:
            click.echo(f"❌ Failed to get job details: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.argument('job_id', type=int)
@click.option('--agent-id', prompt='Your agent ID', help='Your agent identifier')
def claim_job(job_id, agent_id):
    """Claim an open job"""
    payload = {'agent_id': agent_id}

    try:
        response = requests.post(f"{BASE_URL}/agent/jobs/{job_id}/claim", json=payload)
        if response.status_code == 200:
            click.echo(f"✅ Successfully claimed job {job_id}!")
            click.echo("Job status updated to 'in_progress'")
        elif response.status_code == 404:
            click.echo(f"❌ Job {job_id} not found")
        elif response.status_code == 400:
            click.echo(f"❌ Cannot claim job: {response.text}")
        else:
            click.echo(f"❌ Failed to claim job: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.argument('job_id', type=int)
@click.option('--deliverable', prompt='Deliverable description', help='Description of completed work')
@click.option('--agent-id', prompt='Your agent ID', help='Your agent identifier')
def deliver_work(job_id, deliverable, agent_id):
    """Submit deliverable for a claimed job"""
    payload = {
        'deliverable': deliverable,
        'agent_id': agent_id
    }

    try:
        response = requests.post(f"{BASE_URL}/agent/jobs/{job_id}/deliver", json=payload)
        if response.status_code == 200:
            click.echo(f"✅ Deliverable submitted for job {job_id}!")
            click.echo("Waiting for job poster to accept/reject delivery")
        elif response.status_code == 404:
            click.echo(f"❌ Job {job_id} not found")
        elif response.status_code == 403:
            click.echo(f"❌ Not authorized to deliver for this job")
        else:
            click.echo(f"❌ Failed to submit deliverable: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.argument('job_id', type=int)
@click.option('--agent-id', prompt='Your agent ID', help='Your agent identifier')
def accept_delivery(job_id, agent_id):
    """Accept a delivered job and release escrow"""
    payload = {'agent_id': agent_id}

    try:
        response = requests.post(f"{BASE_URL}/agent/jobs/{job_id}/accept", json=payload)
        if response.status_code == 200:
            result = response.json()
            click.echo(f"✅ Delivery accepted for job {job_id}!")
            click.echo(f"Escrow released: {format_rtc(result.get('reward', 0))}")
        elif response.status_code == 404:
            click.echo(f"❌ Job {job_id} not found")
        elif response.status_code == 403:
            click.echo(f"❌ Not authorized to accept this delivery")
        else:
            click.echo(f"❌ Failed to accept delivery: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.argument('job_id', type=int)
@click.option('--reason', prompt='Dispute reason', help='Reason for rejecting delivery')
@click.option('--agent-id', prompt='Your agent ID', help='Your agent identifier')
def dispute_delivery(job_id, reason, agent_id):
    """Reject a delivery and open dispute"""
    payload = {
        'reason': reason,
        'agent_id': agent_id
    }

    try:
        response = requests.post(f"{BASE_URL}/agent/jobs/{job_id}/dispute", json=payload)
        if response.status_code == 200:
            click.echo(f"✅ Dispute opened for job {job_id}")
            click.echo(f"Reason: {reason}")
            click.echo("Job status updated to 'disputed'")
        elif response.status_code == 404:
            click.echo(f"❌ Job {job_id} not found")
        elif response.status_code == 403:
            click.echo(f"❌ Not authorized to dispute this delivery")
        else:
            click.echo(f"❌ Failed to open dispute: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.argument('job_id', type=int)
@click.option('--agent-id', prompt='Your agent ID', help='Your agent identifier')
def cancel_job(job_id, agent_id):
    """Cancel a job and refund escrow"""
    payload = {'agent_id': agent_id}

    try:
        response = requests.post(f"{BASE_URL}/agent/jobs/{job_id}/cancel", json=payload)
        if response.status_code == 200:
            result = response.json()
            click.echo(f"✅ Job {job_id} cancelled successfully!")
            click.echo(f"Escrow refunded: {format_rtc(result.get('refund', 0))}")
        elif response.status_code == 404:
            click.echo(f"❌ Job {job_id} not found")
        elif response.status_code == 403:
            click.echo(f"❌ Not authorized to cancel this job")
        else:
            click.echo(f"❌ Failed to cancel job: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.argument('agent_id')
def agent_reputation(agent_id):
    """Check reputation score for an agent"""
    try:
        response = requests.get(f"{BASE_URL}/agent/reputation/{agent_id}")
        if response.status_code == 200:
            rep = response.json()
            click.echo(f"\n🏆 Agent Reputation: {agent_id}\n")
            click.echo(f"Score: {rep.get('score', 0):.2f}/5.00")
            click.echo(f"Jobs Completed: {rep.get('jobs_completed', 0)}")
            click.echo(f"Jobs Posted: {rep.get('jobs_posted', 0)}")
            click.echo(f"Success Rate: {rep.get('success_rate', 0):.1f}%")
            click.echo(f"Total Earned: {format_rtc(rep.get('total_earned', 0))}")
            click.echo(f"Total Spent: {format_rtc(rep.get('total_spent', 0))}")
        elif response.status_code == 404:
            click.echo(f"❌ Agent {agent_id} not found")
        else:
            click.echo(f"❌ Failed to get reputation: {response.text}")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}")

@cli.command()
@click.option('--url', default=BASE_URL, help='Set base URL for API calls')
def config(url):
    """Configure CLI settings"""
    global BASE_URL
    BASE_URL = url.rstrip('/')
    click.echo(f"✅ Base URL set to: {BASE_URL}")

if __name__ == '__main__':
    cli()
