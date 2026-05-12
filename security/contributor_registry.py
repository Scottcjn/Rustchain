"""
Add admin authorization check for contributor registry approval route
"""
import functools
from typing import Callable, Dict, Any
from flask import request, session, abort


def require_admin(f: Callable) -> Callable:
    """Decorator to require admin authorization"""
    
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated
        if 'user_id' not in session:
            abort(401, 'Authentication required')
        
        # Check if user is admin
        user_role = session.get('user_role')
        if user_role != 'admin':
            abort(403, 'Admin authorization required')
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_auth(f: Callable) -> Callable:
    """Decorator to require authentication"""
    
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            abort(401, 'Authentication required')
        
        return f(*args, **kwargs)
    
    return decorated_function


class ContributorRegistry:
    """Manage contributor registry with proper authorization"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    @require_admin
    def approve_contributor(self, contributor_id: int, approved: bool) -> Dict[str, Any]:
        """Approve or reject a contributor (admin only)"""
        if not self._is_admin(session.get('user_id')):
            abort(403, 'Admin authorization required')
        
        # Update contributor status
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE contributors SET approved = ?, approved_by = ?, approved_at = ? WHERE id = ?",
            (1 if approved else 0, session.get('user_id'), time.time(), contributor_id)
        )
        self.db.commit()
        
        return {
            'success': True,
            'contributor_id': contributor_id,
            'approved': approved
        }
    
    @require_auth
    def get_contributor(self, contributor_id: int) -> Dict[str, Any]:
        """Get contributor details (authenticated users only)"""
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM contributors WHERE id = ?", (contributor_id,))
        row = cursor.fetchone()
        
        if not row:
            abort(404, 'Contributor not found')
        
        return dict(row)
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        cursor = self.db.cursor()
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        
        return row and row[0] == 'admin'
    
    def get_pending_contributors(self) -> list:
        """Get pending contributors (admin only)"""
        if not self._is_admin(session.get('user_id')):
            abort(403, 'Admin authorization required')
        
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM contributors WHERE approved = 0")
        
        return [dict(row) for row in cursor.fetchall()]


def setup_routes(app, db_connection):
    """Setup routes with proper authorization"""
    registry = ContributorRegistry(db_connection)
    
    @app.route('/api/contributors/approve', methods=['POST'])
    @require_admin
    def approve_contributor():
        """Approve contributor endpoint (admin only)"""
        data = request.get_json()
        contributor_id = data.get('contributor_id')
        approved = data.get('approved', True)
        
        if not contributor_id:
            abort(400, 'contributor_id required')
        
        return registry.approve_contributor(contributor_id, approved)
    
    @app.route('/api/contributors/<int:contributor_id>')
    @require_auth
    def get_contributor(contributor_id):
        """Get contributor details"""
        return registry.get_contributor(contributor_id)
    
    @app.route('/api/contributors/pending')
    @require_admin
    def get_pending_contributors():
        """Get pending contributors (admin only)"""
        return {'contributors': registry.get_pending_contributors()}
