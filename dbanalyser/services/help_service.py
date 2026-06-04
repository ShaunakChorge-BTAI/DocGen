"""
Phase 3: Help Service
Handles help articles, knowledge base, and search functionality
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import text

logger = logging.getLogger(__name__)


class HelpService:
    """Service for help article management and search"""

    def __init__(self, db):
        self.db = db

    def create_help_article(
        self,
        title: str,
        content: str,
        category: str,
        tags: str,
        user_id: int,
        is_published: bool = True
    ) -> Dict:
        """Create a new help article"""
        try:
            # Generate slug from title
            slug = title.lower().replace(" ", "-").replace("_", "-")
            slug = "".join(c for c in slug if c.isalnum() or c == "-")[:100]

            query = text("""
                INSERT INTO help_articles
                (title, slug, content, category, tags, created_by_user_id, is_published)
                VALUES (:title, :slug, :content, :category, :tags, :user_id, :published)
                RETURNING id, title, slug, category
            """)
            result = self.db.execute(query, {
                "title": title,
                "slug": slug,
                "content": content,
                "category": category,
                "tags": tags,
                "user_id": user_id,
                "published": is_published
            })
            row = result.fetchone()
            self.db.commit()

            return {
                "article_id": row[0],
                "title": row[1],
                "slug": row[2],
                "category": row[3],
                "status": "created"
            }
        except Exception as e:
            logger.error(f"Error creating help article: {e}")
            raise

    def search_articles(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Full-text search for help articles"""
        try:
            if category:
                search_query = text("""
                    SELECT id, title, slug, category, view_count, helpful_votes
                    FROM help_articles
                    WHERE is_published = true
                    AND category = :category
                    AND (
                        title ILIKE :query
                        OR content ILIKE :query
                        OR tags ILIKE :query
                    )
                    ORDER BY view_count DESC, helpful_votes DESC
                    LIMIT :limit
                """)
                results = self.db.execute(search_query, {
                    "query": f"%{query}%",
                    "category": category,
                    "limit": limit
                })
            else:
                search_query = text("""
                    SELECT id, title, slug, category, view_count, helpful_votes
                    FROM help_articles
                    WHERE is_published = true
                    AND (
                        title ILIKE :query
                        OR content ILIKE :query
                        OR tags ILIKE :query
                    )
                    ORDER BY view_count DESC, helpful_votes DESC
                    LIMIT :limit
                """)
                results = self.db.execute(search_query, {
                    "query": f"%{query}%",
                    "limit": limit
                })

            articles = []
            for row in results:
                articles.append({
                    "article_id": row[0],
                    "title": row[1],
                    "slug": row[2],
                    "category": row[3],
                    "view_count": row[4],
                    "helpful_votes": row[5]
                })
            return articles
        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            return []

    def get_article_by_slug(self, slug: str) -> Optional[Dict]:
        """Retrieve article by slug and increment view count"""
        try:
            query = text("""
                SELECT id, title, content, category, tags, view_count, helpful_votes
                FROM help_articles
                WHERE slug = :slug AND is_published = true
            """)
            result = self.db.execute(query, {"slug": slug})
            row = result.fetchone()

            if row:
                article_id = row[0]

                # Increment view count
                update_query = text("""
                    UPDATE help_articles
                    SET view_count = view_count + 1
                    WHERE id = :id
                """)
                self.db.execute(update_query, {"id": article_id})
                self.db.commit()

                return {
                    "article_id": article_id,
                    "title": row[1],
                    "content": row[2],
                    "category": row[3],
                    "tags": row[4],
                    "view_count": row[5] + 1,
                    "helpful_votes": row[6]
                }
            return None
        except Exception as e:
            logger.error(f"Error retrieving article: {e}")
            return None

    def record_helpful_vote(self, article_id: int, is_helpful: bool) -> Dict:
        """Record helpful/not helpful vote"""
        try:
            if is_helpful:
                update_query = text("""
                    UPDATE help_articles
                    SET helpful_votes = helpful_votes + 1
                    WHERE id = :id
                    RETURNING helpful_votes
                """)
            else:
                update_query = text("""
                    UPDATE help_articles
                    SET helpful_votes = CASE WHEN helpful_votes > 0 THEN helpful_votes - 1 ELSE 0 END
                    WHERE id = :id
                    RETURNING helpful_votes
                """)

            result = self.db.execute(update_query, {"id": article_id})
            row = result.fetchone()
            self.db.commit()

            return {
                "article_id": article_id,
                "helpful_votes": row[0] if row else 0,
                "vote_recorded": True
            }
        except Exception as e:
            logger.error(f"Error recording vote: {e}")
            raise

    def submit_article_feedback(
        self,
        article_id: int,
        user_id: Optional[int],
        feedback_type: str,
        feedback_text: Optional[str] = None
    ) -> Dict:
        """Submit feedback on an article"""
        try:
            query = text("""
                INSERT INTO help_article_feedback
                (article_id, user_id, feedback_type, feedback_text)
                VALUES (:article_id, :user_id, :feedback_type, :feedback_text)
                RETURNING id, created_at
            """)
            result = self.db.execute(query, {
                "article_id": article_id,
                "user_id": user_id,
                "feedback_type": feedback_type,
                "feedback_text": feedback_text
            })
            row = result.fetchone()
            self.db.commit()

            return {
                "feedback_id": row[0],
                "article_id": article_id,
                "feedback_type": feedback_type,
                "created_at": str(row[1]),
                "status": "recorded"
            }
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            raise

    def get_articles_by_category(self, category: str, limit: int = 20) -> List[Dict]:
        """Get all articles in a category"""
        try:
            query = text("""
                SELECT id, title, slug, category, view_count, helpful_votes
                FROM help_articles
                WHERE category = :category AND is_published = true
                ORDER BY view_count DESC, created_at DESC
                LIMIT :limit
            """)
            results = self.db.execute(query, {
                "category": category,
                "limit": limit
            })

            articles = []
            for row in results:
                articles.append({
                    "article_id": row[0],
                    "title": row[1],
                    "slug": row[2],
                    "category": row[3],
                    "view_count": row[4],
                    "helpful_votes": row[5]
                })
            return articles
        except Exception as e:
            logger.error(f"Error retrieving articles by category: {e}")
            return []

    def get_trending_articles(self, limit: int = 10) -> List[Dict]:
        """Get trending articles by view count"""
        try:
            query = text("""
                SELECT id, title, slug, category, view_count, helpful_votes
                FROM help_articles
                WHERE is_published = true
                AND created_at >= NOW() - INTERVAL '30 days'
                ORDER BY view_count DESC
                LIMIT :limit
            """)
            results = self.db.execute(query, {"limit": limit})

            articles = []
            for row in results:
                articles.append({
                    "article_id": row[0],
                    "title": row[1],
                    "slug": row[2],
                    "category": row[3],
                    "view_count": row[4],
                    "helpful_votes": row[5]
                })
            return articles
        except Exception as e:
            logger.error(f"Error retrieving trending articles: {e}")
            return []

    def get_popular_articles(self, limit: int = 10) -> List[Dict]:
        """Get articles with highest helpful votes"""
        try:
            query = text("""
                SELECT id, title, slug, category, view_count, helpful_votes
                FROM help_articles
                WHERE is_published = true
                ORDER BY helpful_votes DESC, view_count DESC
                LIMIT :limit
            """)
            results = self.db.execute(query, {"limit": limit})

            articles = []
            for row in results:
                articles.append({
                    "article_id": row[0],
                    "title": row[1],
                    "slug": row[2],
                    "category": row[3],
                    "view_count": row[4],
                    "helpful_votes": row[5]
                })
            return articles
        except Exception as e:
            logger.error(f"Error retrieving popular articles: {e}")
            return []

    def get_article_feedback(self, article_id: int, limit: int = 50) -> List[Dict]:
        """Get feedback for an article"""
        try:
            query = text("""
                SELECT id, feedback_type, feedback_text, created_at
                FROM help_article_feedback
                WHERE article_id = :article_id
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            results = self.db.execute(query, {
                "article_id": article_id,
                "limit": limit
            })

            feedback_list = []
            for row in results:
                feedback_list.append({
                    "feedback_id": row[0],
                    "feedback_type": row[1],
                    "feedback_text": row[2],
                    "created_at": str(row[3])
                })
            return feedback_list
        except Exception as e:
            logger.error(f"Error retrieving feedback: {e}")
            return []

    def update_article(
        self,
        article_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        is_published: Optional[bool] = None
    ) -> Dict:
        """Update an existing article"""
        try:
            updates = []
            params = {"article_id": article_id}

            if title is not None:
                updates.append("title = :title")
                params["title"] = title
            if content is not None:
                updates.append("content = :content")
                params["content"] = content
            if category is not None:
                updates.append("category = :category")
                params["category"] = category
            if tags is not None:
                updates.append("tags = :tags")
                params["tags"] = tags
            if is_published is not None:
                updates.append("is_published = :published")
                params["published"] = is_published

            if not updates:
                return {"status": "no_changes"}

            updates.append("updated_at = NOW()")
            update_query = text(f"""
                UPDATE help_articles
                SET {", ".join(updates)}
                WHERE id = :article_id
                RETURNING id, title, category
            """)

            result = self.db.execute(update_query, params)
            row = result.fetchone()
            self.db.commit()

            return {
                "article_id": row[0],
                "title": row[1],
                "category": row[2],
                "status": "updated"
            }
        except Exception as e:
            logger.error(f"Error updating article: {e}")
            raise
