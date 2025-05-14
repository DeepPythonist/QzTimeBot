from typing import Dict, List, Any, Optional, Union
import datetime
import logging
import random
import string
import uuid
import config
from pymongo import MongoClient
from pymongo.database import Database
from bson.int64 import Int64

logger = logging.getLogger(__name__)

class Database:
    """
    MongoDB database manager for the QuizBot application.
    
    Handles all database operations including user management, topics, questions,
    statistics, and file storage.
    """
    
    def __init__(self, connection_string: str = None, database_name: str = None):
        """
        Initialize database connection.
        
        Args:
            connection_string (str, optional): MongoDB connection string. Defaults to config.MONGO_URL.
            database_name (str, optional): Name of the database. Defaults to config.MONGO_DB_NAME.
        """
        self.client = MongoClient(connection_string or config.MONGO_URL)
        self.db: Database = self.client[database_name or config.MONGO_DB_NAME]
        
        # Collections
        self.users = self.db["users"]
        self.topics = self.db["topics"]
        self.questions = self.db["questions"]

    def create_user(self, user_id: str, username: str = None, full_name: str = "", has_start: bool = None) -> Dict[str, Any]:
        """
        Create a new user or update an existing one.
        
        Args:
            user_id (str): User ID from Telegram
            username (str, optional): Username from Telegram
            full_name (str, optional): Full name from Telegram
            has_start (bool, optional): Whether user has started the bot
            
        Returns:
            Dict[str, Any]: Dictionary with user data and exists flag
            
        Raises:
            Exception: If database operation fails
        """
        try:
            now = datetime.datetime.now()
            existing_user = self.users.find_one({"user_id": user_id})

            if existing_user:
                update_fields = {"updated_at": now}

                if has_start is not None:
                    update_fields["has_start"] = has_start

                self.users.update_one(
                    {"user_id": user_id},
                    {"$set": update_fields}
                )

                updated_user = self.users.find_one({"user_id": user_id})
                logger.debug(f"User {user_id} updated")
                return {"exists": True, "user_data": updated_user}

            new_user = {
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "has_start": has_start,
                "stats": {
                    "total_quiz": 0,
                    "total_correct": 0,
                    "total_wrong": 0,
                    "total_points": 0,
                    "quiz_created": 0,
                },
                "created_at": now,
                "updated_at": now
            }

            result = self.users.insert_one(new_user)
            new_user["_id"] = result.inserted_id

            logger.debug(f"User {user_id} created")
            return {"exists": False, "user_data": new_user}

        except Exception as e:
            logger.error(f"Failed to create or update user: {e}")
            raise Exception(f"Failed to create or update user: {e}")

    def get_user_by_id(self, user_id: str) -> Dict[str, Any]:
        """
        Get a user by their ID.
        
        Args:
            user_id (str): User ID to search for
            
        Returns:
            Dict[str, Any]: Success status and user data if found
        """
        try:
            user_id_long = Int64(int(user_id))
            user = self.users.find_one({"user_id": user_id_long})
            if user:
                return {"status": "success", "user": user}
        except:
            pass
        
        user = self.users.find_one({"user_id": user_id})
        if not user:
            logger.debug(f"User not found with either numeric or string ID: {user_id}")
            return {"status": "error", "message": "User not found"}

        return {"status": "success", "user": user}

    def get_all_users(self, has_start: bool = False) -> List[Dict[str, Any]]:
        """
        Get all users or only those who have started the bot.
        
        Args:
            has_start (bool, optional): Filter users by has_start flag
            
        Returns:
            List[Dict[str, Any]]: List of user documents
        """
        if has_start:
            users = self.users.find({"has_start": True})
        else:
            users = self.users.find({})
        return list(users)

    def get_count_of_users(self) -> int:
        """
        Get total number of users.
        
        Returns:
            int: Count of all users
        """
        count = self.users.count_documents({})
        return count

    def get_count_of_started_users(self) -> int:
        """
        Get number of users who have started the bot.
        
        Returns:
            int: Count of users with has_start=True
        """
        count = self.users.count_documents({"has_start": True})
        return count

    def get_count_today_users(self) -> int:
        """
        Get number of users created today.
        
        Returns:
            int: Count of users created today
        """
        
        today_start = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time.min)
        
        today_end = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time.max)
        
        count = self.users.count_documents({
            "created_at": {
                "$gte": today_start,
                "$lte": today_end
            }
        })
        
        return count

    def create_topic(self, topic_name: str, topic_description: str = "") -> Dict[str, Any]:
        """
        Create a new topic in the database.
        
        Args:
            topic_name (str): Name of the topic
            topic_description (str, optional): Description of the topic
            
        Returns:
            Dict[str, Any]: Status and topic data if successful
            
        Raises:
            ValueError: If topic name or description doesn't meet requirements
        """
        if not topic_name or not isinstance(topic_name, str):
            raise ValueError("Topic name cannot be empty")

        if len(topic_name) < config.TOPIC_NAME_MIN_LENGTH or len(topic_name) > config.TOPIC_NAME_MAX_LENGTH:
            raise ValueError(
                f"Topic name must be between {config.TOPIC_NAME_MIN_LENGTH} and {config.TOPIC_NAME_MAX_LENGTH} characters")

        if not isinstance(topic_description, str):
            raise ValueError("Topic description must be a string")

        if topic_description and (len(topic_description) < config.TOPIC_DESCRIPTION_MIN_LENGTH or len(
                topic_description) > config.TOPIC_DESCRIPTION_MAX_LENGTH):
            raise ValueError(
                f"Topic description must be between {config.TOPIC_DESCRIPTION_MIN_LENGTH} and {config.TOPIC_DESCRIPTION_MAX_LENGTH} characters")

        existing_topic = self.topics.find_one({"name": topic_name})
        if existing_topic:
            return {"status": "error", "message": "A topic with this name already exists"}

        topic_id = str(uuid.uuid4())[:8]
        now = datetime.datetime.now()
        topic_data = {
            "topic_id": topic_id,
            "name": topic_name,
            "description": topic_description,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "stats": {
                "topic_played": 0,
            }
        }

        try:
            result = self.topics.insert_one(topic_data)

            topic_data["_id"] = result.inserted_id
            logger.debug(f"Topic '{topic_name}' created with ID: {topic_id}")

            return {
                "status": "success",
                "message": "Topic created successfully",
                "topic": topic_data
            }
        except Exception as e:
            logger.error(f"Error creating topic: {str(e)}")
            return {
                "status": "error",
                "message": f"Error creating topic: {str(e)}"
            }

    def get_all_topics(self) -> List[Dict[str, Any]]:
        """
        Get all topics from the database.
        
        Returns:
            List[Dict[str, Any]]: List of all topic documents
        """
        topics = self.topics.find()
        return list(topics)

    def get_topic_by_id(self, topic_id: str) -> Dict[str, Any]:
        """
        Get a topic by its ID.
        
        Args:
            topic_id (str): ID of the topic to retrieve
            
        Returns:
            Dict[str, Any]: Status and topic data if found
        """
        topic = self.topics.find_one({"topic_id": topic_id})
        if not topic:
            return {"status": "error", "message": "Topic not found"}

        return {"status": "success", "topic": topic}

    def get_topic_by_name(self, topic_name: str) -> Dict[str, Any]:
        """
        Get a topic by its name.
        
        Args:
            topic_name (str): Name of the topic to retrieve
            
        Returns:
            Dict[str, Any]: Status and topic data if found
        """
        topic = self.topics.find_one({"name": topic_name})
        if not topic:
            return {"status": "error", "message": "Topic not found"}

        return {"status": "success", "topic": topic}

    def edit_topic_name(self, topic_id: str, new_name: str) -> Dict[str, Any]:
        """
        Update a topic's name.
        
        Args:
            topic_id (str): ID of the topic to update
            new_name (str): New name for the topic
            
        Returns:
            Dict[str, Any]: Status and message
        """
        topic = self.topics.find_one({"topic_id": topic_id})
        if not topic:
            return {"status": "error", "message": "Topic not found"}

        try:
            self.topics.update_one({"topic_id": topic_id}, {"$set": {"name": new_name}})
            logger.debug(f"Topic {topic_id} name updated to '{new_name}'")
            return {"status": "success", "message": "Topic name updated successfully"}
        except Exception as e:
            logger.error(f"Error updating topic name: {str(e)}")
            return {"status": "error", "message": f"Failed to update topic name: {str(e)}"}

    def edit_topic_description(self, topic_id: str, new_description: str) -> Dict[str, Any]:
        """
        Update a topic's description.
        
        Args:
            topic_id (str): ID of the topic to update
            new_description (str): New description for the topic
            
        Returns:
            Dict[str, Any]: Status and message
        """
        topic = self.topics.find_one({"topic_id": topic_id})
        if not topic:
            return {"status": "error", "message": "Topic not found"}

        try:
            self.topics.update_one({"topic_id": topic_id}, {"$set": {"description": new_description}})
            logger.debug(f"Topic {topic_id} description updated")
            return {"status": "success", "message": "Topic description updated successfully"}
        except Exception as e:
            logger.error(f"Error updating topic description: {str(e)}")
            return {"status": "error", "message": f"Failed to update topic description: {str(e)}"}

    def edit_topic_active_status(self, topic_id: str, new_active_status: bool) -> Dict[str, Any]:
        """
        Update a topic's active status.
        
        Args:
            topic_id (str): ID of the topic to update
            new_active_status (bool): New active status for the topic
            
        Returns:
            Dict[str, Any]: Status and message
        """
        topic = self.topics.find_one({"topic_id": topic_id})
        if not topic:
            return {"status": "error", "message": "Topic not found"}

        try:
            self.topics.update_one({"topic_id": topic_id}, {"$set": {"is_active": new_active_status}})
            status_str = "activated" if new_active_status else "deactivated"
            logger.debug(f"Topic {topic_id} {status_str}")
            return {"status": "success", "message": f"Topic {status_str} successfully"}
        except Exception as e:
            logger.error(f"Error updating topic active status: {str(e)}")
            return {"status": "error", "message": f"Failed to update topic status: {str(e)}"}

    def delete_topic(self, topic_id: str) -> Dict[str, Any]:
        """
        Delete a topic and all associated questions.
        
        Args:
            topic_id (str): ID of the topic to delete
            
        Returns:
            Dict[str, Any]: Status and message
        """
        topic = self.topics.find_one({"topic_id": topic_id})
        if not topic:
            return {"status": "error", "message": "Topic not found"}

        try:
            questions_deleted = self.questions.delete_many({"topic_id": topic_id})
            
            self.topics.delete_one({"topic_id": topic_id})
            logger.debug(f"Topic {topic_id} deleted with {questions_deleted.deleted_count} associated questions")
            
            return {
                "status": "success", 
                "message": f"Topic deleted successfully along with {questions_deleted.deleted_count} associated questions"
            }
        except Exception as e:
            logger.error(f"Error deleting topic: {str(e)}")
            return {"status": "error", "message": f"Failed to delete topic: {str(e)}"}

    def create_question(self, topic_id: str, question_text: str, options: list, correct_option: int,
                        created_by: str, is_approved: bool = False) -> Dict[str, Any]:
        """
        Create a new question in the database.
        
        Args:
            topic_id (str): ID of the topic this question belongs to
            question_text (str): The question text
            options (list): List of options (answers)
            correct_option (int): Index of the correct option (0-based)
            created_by (str): User ID of who created the question
            is_approved (bool): Whether the question is approved (admin-created questions are auto-approved)
            
        Returns:
            Dict[str, Any]: Created question information or error message
        """
        try:
            if not question_text or not isinstance(question_text, str):
                return {"status": "error", "message": "Question text cannot be empty"}

            if len(question_text) < config.QUESTION_MIN_LENGTH or len(question_text) > config.QUESTION_MAX_LENGTH:
                return {"status": "error",
                        "message": f"Question text must be between {config.QUESTION_MIN_LENGTH} and {config.QUESTION_MAX_LENGTH} characters"}

            if not options or len(options) != config.OPTION_COUNT:
                return {"status": "error", "message": f"Question must have exactly {config.OPTION_COUNT} options"}

            for i, option in enumerate(options):
                if not option or not isinstance(option, str):
                    return {"status": "error", "message": f"Option {i + 1} cannot be empty"}

                if len(option) < config.OPTION_MIN_LENGTH or len(option) > config.OPTION_MAX_LENGTH:
                    return {"status": "error",
                            "message": f"Option {i + 1} must be between {config.OPTION_MIN_LENGTH} and {config.OPTION_MAX_LENGTH} characters"}

            if correct_option < 0 or correct_option >= len(options):
                return {"status": "error", "message": f"Correct option index must be between 0 and {len(options) - 1}"}

            topic = self.topics.find_one({"topic_id": topic_id})
            if not topic:
                return {"status": "error", "message": "Topic not found"}

            question_id = str(uuid.uuid4())[:8]

            now = datetime.datetime.now()
            question_data = {
                "question_id": question_id,
                "topic_id": topic_id,
                "text": question_text,
                "options": options,
                "correct_option": correct_option,
                "created_by": created_by,
                "is_approved": is_approved,
                "created_at": now,
                "updated_at": now
            }

            result = self.questions.insert_one(question_data)

            question_data["_id"] = result.inserted_id

            if is_approved:
                self.topics.update_one(
                    {"topic_id": topic_id},
                    {"$inc": {"question_count": 1}}
                )
                logger.debug(f"Question {question_id} created and approved for topic {topic_id}")
            else:
                logger.debug(f"Question {question_id} created but pending approval for topic {topic_id}")

            return {
                "status": "success",
                "message": "Question created successfully",
                "question": question_data
            }

        except Exception as e:
            logger.error(f"Error creating question: {str(e)}")
            return {
                "status": "error",
                "message": f"Error creating question: {str(e)}"
            }

    def get_question_by_id(self, question_id: str) -> Dict[str, Any]:
        """
        Get a question by its ID.
        
        Args:
            question_id (str): ID of the question to retrieve
            
        Returns:
            Dict[str, Any]: Success status and question data if found
        """
        question = self.questions.find_one({"question_id": question_id})
        if not question:
            return {"status": "error", "message": "Question not found"}

        return {"status": "success", "question": question}

    def get_questions_by_topic(self, topic_id: str, only_approved: bool = True) -> Dict[str, Any]:
        """
        Get all questions for a specific topic.
        
        Args:
            topic_id (str): ID of the topic
            only_approved (bool, optional): Whether to return only approved questions
            
        Returns:
            Dict[str, Any]: Success status and list of questions
        """
        query = {"topic_id": topic_id}
        if only_approved:
            query["is_approved"] = True

        questions = self.questions.find(query)
        questions_list = list(questions)

        if not questions_list:
            return {"status": "error", "message": "No questions found for this topic"}

        return {"status": "success", "questions": questions_list}

    def get_pending_questions(self) -> Dict[str, Any]:
        """
        Get all questions pending approval.
        
        Returns:
            Dict[str, Any]: Success status and list of pending questions
        """
        questions = self.questions.find({"is_approved": False})
        questions_list = list(questions)

        if not questions_list:
            return {"status": "error", "message": "No pending questions found"}

        return {"status": "success", "questions": questions_list}

    def approve_question(self, question_id: str) -> Dict[str, Any]:
        """
        Approve a question.
        
        Args:
            question_id (str): ID of the question to approve
            
        Returns:
            Dict[str, Any]: Success status and message
        """
        question = self.questions.find_one({"question_id": question_id})
        if not question:
            return {"status": "error", "message": "Question not found"}

        if question["is_approved"]:
            return {"status": "error", "message": "Question is already approved"}

        try:
            self.questions.update_one(
                {"question_id": question_id},
                {"$set": {"is_approved": True, "updated_at": datetime.datetime.now()}}
            )

            self.topics.update_one(
                {"topic_id": question["topic_id"]},
                {"$inc": {"question_count": 1}}
            )
            
            logger.debug(f"Question {question_id} approved for topic {question['topic_id']}")
            return {"status": "success", "message": "Question approved successfully"}
        except Exception as e:
            logger.error(f"Error approving question: {str(e)}")
            return {"status": "error", "message": f"Failed to approve question: {str(e)}"}

    def reject_question(self, question_id: str) -> Dict[str, Any]:
        """
        Reject and delete a question.
        
        Args:
            question_id (str): ID of the question to reject
            
        Returns:
            Dict[str, Any]: Success status and message
        """
        question = self.questions.find_one({"question_id": question_id})
        if not question:
            return {"status": "error", "message": "Question not found"}

        try:
            self.questions.delete_one({"question_id": question_id})
            logger.debug(f"Question {question_id} rejected and deleted")
            return {"status": "success", "message": "Question rejected and deleted successfully"}
        except Exception as e:
            logger.error(f"Error rejecting question: {str(e)}")
            return {"status": "error", "message": f"Failed to reject question: {str(e)}"}
    

    def update_user_stats(self, user_id: str, correct_count: int, wrong_count: int, points: int) -> Dict[str, Any]:
        """
        Update user statistics after completing a quiz.
        
        Args:
            user_id (str): ID of the user
            correct_count (int): Number of correct answers
            wrong_count (int): Number of wrong answers
            points (int): Points earned in this quiz
            
        Returns:
            Dict[str, Any]: Status and message
        """
        try:
            try:
                user_id_long = Int64(int(user_id))
                user = self.users.find_one({"user_id": user_id_long})
                if user:
                    result = self.users.update_one(
                        {"user_id": user_id_long},
                        {"$inc": {"stats.total_quiz": 1, "stats.total_correct": correct_count, "stats.total_wrong": wrong_count, "stats.total_points": points}}
                    )
                else:
                    user = self.users.find_one({"user_id": user_id})
                    if not user:
                        logger.warning(f"User {user_id} not found for updating stats")
                        return {"status": "error", "message": "User not found"}
                    
                    result = self.users.update_one(
                        {"user_id": user_id},
                        {"$inc": {"stats.total_quiz": 1, "stats.total_correct": correct_count, "stats.total_wrong": wrong_count, "stats.total_points": points}}
                    )
            except:
                user = self.users.find_one({"user_id": user_id})
                if not user:
                    logger.warning(f"User {user_id} not found for updating stats")
                    return {"status": "error", "message": "User not found"}
                
                result = self.users.update_one(
                    {"user_id": user_id},
                    {"$inc": {"stats.total_quiz": 1, "stats.total_correct": correct_count, "stats.total_wrong": wrong_count, "stats.total_points": points}}
                )
            
            if result.modified_count == 1:
                logger.debug(f"User {user_id} stats updated: +{correct_count} correct, +{wrong_count} wrong, +{points} points")
                return {"status": "success", "message": "User stats updated successfully"}
            else:
                logger.warning(f"No changes made to user {user_id} stats")
                return {"status": "warning", "message": "No changes made to user stats"}
                
        except Exception as e:
            logger.error(f"Error updating user stats: {str(e)}")
            return {"status": "error", "message": f"Failed to update user stats: {str(e)}"}
        

    def update_quiz_created(self, user_id: str) -> Dict[str, Any]:
        """
        Increment the quiz_created counter for a user.
        
        Args:
            user_id (str): ID of the user who created the quiz
            
        Returns:
            Dict[str, Any]: Status and message
        """
        try:
            try:
                user_id_int = Int64(int(user_id))
                user = self.users.find_one({"user_id": user_id_int})
                if user:
                    update_query = {}
                    if "stats" not in user:
                        update_query["stats"] = {"quiz_created": 1}
                    else:
                        update_query = {"$inc": {"stats.quiz_created": 1}}
                    
                    self.users.update_one({"user_id": user_id_int}, update_query)
                    logger.debug(f"Updated quiz_created for user {user_id} (numeric)")
                    return {"status": "success", "message": "Quiz created updated successfully"}
            except:
                pass
                
            user = self.users.find_one({"user_id": user_id})
            if user:
                update_query = {}
                if "stats" not in user:
                    update_query["stats"] = {"quiz_created": 1}
                else:
                    update_query = {"$inc": {"stats.quiz_created": 1}}
                
                self.users.update_one({"user_id": user_id}, update_query)
                logger.debug(f"Updated quiz_created for user {user_id} (string)")
                return {"status": "success", "message": "Quiz created updated successfully"}
            else:
                logger.warning(f"User not found for updating quiz_created: {user_id}")
                return {"status": "warning", "message": "User not found"}
                
        except Exception as e:
            logger.error(f"Error updating quiz created: {str(e)}")
            return {"status": "error", "message": f"Failed to update quiz created: {str(e)}"}
        

    def update_topic_played(self, topic_id: str) -> Dict[str, Any]:
        """
        Increment the play count for a topic.
        
        Args:
            topic_id (str): ID of the topic played
            
        Returns:
            Dict[str, Any]: Status and message
        """
        try:
            topic = self.topics.find_one({"topic_id": topic_id})
            if not topic:
                logger.warning(f"Topic not found for updating topic_played: {topic_id}")
                return {"status": "warning", "message": "Topic not found"}
            
           
            update_query = {}
            if "stats" not in topic:
                update_query["$set"] = {"stats": {"topic_played": 1}}
            else:
                if "topic_played" not in topic["stats"]:
                    update_query["$set"] = {"stats.topic_played": 1}
                else:
                    update_query["$inc"] = {"stats.topic_played": 1}
            
            self.topics.update_one({"topic_id": topic_id}, update_query)
            logger.debug(f"Updated topic_played for topic {topic_id}")
            return {"status": "success", "message": "Topic played updated successfully"}
        except Exception as e:
            logger.error(f"Error updating topic played: {str(e)}")
            return {"status": "error", "message": f"Failed to update topic played: {str(e)}"}
        

    def get_user_submitted_questions_count(self, user_id: str) -> Dict[str, Any]:
        """
        Get the count of questions submitted by a user.
        
        Args:
            user_id (str): User ID
            
        Returns:
            Dict[str, Any]: Status and count of submitted questions
        """
        try:
            count = self.questions.count_documents({"created_by": str(user_id)})
            
            return {
                "status": "success", 
                "count": count
            }
        except Exception as e:
            logger.error(f"Error getting user submitted questions count: {str(e)}")
            return {
                "status": "error", 
                "message": f"Failed to get user submitted questions count: {str(e)}"
            }

    def get_bot_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the bot and its usage.
        
        Collects statistics including:
        - User stats (total, active, new in last 24h)
        - Topic stats (total, active)
        - Question stats (total, approved, pending)
        - Most popular topics (top 3)
        - Top question submitters (top 3)
        - Top quiz creators (top 3)
        - Questions per topic
        - Questions with invalid topics
        
        Returns:
            Dict[str, Any]: Dictionary with status and statistics or error message
        """
        try:
            users_count = self.get_count_of_users()
            started_users_count = self.get_count_of_started_users()
            today_users_count = self.get_count_today_users()
            
            topics_count = self.topics.count_documents({})
            active_topics_count = self.topics.count_documents({"is_active": True})
            
            total_questions = self.questions.count_documents({})
            approved_questions = self.questions.count_documents({"is_approved": True})
            pending_questions = self.questions.count_documents({"is_approved": False})
            
            popular_topics = []
            popular_topics_data = list(self.topics.find(
                {}, 
                {"topic_id": 1, "name": 1, "stats": 1}
            ).sort([("stats.topic_played", -1)]).limit(3))
            
            for topic in popular_topics_data:
                topic_played = 0
                if "stats" in topic and "topic_played" in topic["stats"]:
                    topic_played = topic["stats"]["topic_played"]
                
                popular_topics.append({
                    "topic_id": topic["topic_id"],
                    "topic_name": topic["name"],
                    "play_count": topic_played
                })
            
            top_submitters = []
            pipeline = [
                {"$group": {"_id": "$created_by", "question_count": {"$sum": 1}}},
                {"$sort": {"question_count": -1}},
                {"$limit": 3}
            ]
            
            submitters_data = list(self.questions.aggregate(pipeline))
            
            for submitter in submitters_data:
                user_id = submitter["_id"]
                count = submitter["question_count"]
                
                user_name = None
                user = self.get_user_by_id(str(user_id))
                if user["status"] == "success" and user["user"]:
                    user_data = user["user"]
                    
                    if "full_name" in user_data and user_data["full_name"]:
                        user_name = user_data["full_name"]
                    elif "username" in user_data and user_data["username"]:
                        user_name = f"@{user_data['username']}"
                
                top_submitters.append({
                    "user_id": user_id,
                    "full_name": user_name,
                    "question_count": count
                })
            
            top_creators = []
            
            quiz_creators_count = self.users.count_documents({"stats.quiz_created": {"$exists": True, "$gt": 0}})
            
            creators_pipeline = [
                {"$match": {"stats.quiz_created": {"$exists": True, "$gt": 0}}},
                {"$sort": {"stats.quiz_created": -1}},
                {"$limit": 3},
                {"$project": {"user_id": 1, "full_name": 1, "username": 1, "quiz_count": "$stats.quiz_created"}}
            ]
            
            creators_data = list(self.users.aggregate(creators_pipeline))
            
            for creator in creators_data:
                user_id = creator["user_id"]
                quiz_count = creator.get("quiz_count", 0)
                
                user_name = None
                if "full_name" in creator and creator["full_name"]:
                    user_name = creator["full_name"]
                elif "username" in creator and creator["username"]:
                    user_name = f"@{creator['username']}"
                
                top_creators.append({
                    "user_id": user_id,
                    "full_name": user_name,
                    "quiz_count": quiz_count
                })
            
            if not top_creators:
                all_users = list(self.users.find())
                users_with_quizzes = []
                
                for user in all_users:
                    if "stats" in user and "quiz_created" in user["stats"] and user["stats"]["quiz_created"] > 0:
                        users_with_quizzes.append({
                            "user_id": user["user_id"],
                            "full_name": user.get("full_name"),
                            "username": user.get("username"),
                            "quiz_count": user["stats"]["quiz_created"]
                        })
                
                users_with_quizzes.sort(key=lambda x: x["quiz_count"], reverse=True)
                
                for creator in users_with_quizzes[:3]:
                    user_id = creator["user_id"]
                    quiz_count = creator["quiz_count"]
                    
                    user_name = None
                    if creator["full_name"]:
                        user_name = creator["full_name"]
                    elif creator["username"]:
                        user_name = f"@{creator['username']}"
                    
                    top_creators.append({
                        "user_id": user_id,
                        "full_name": user_name,
                        "quiz_count": quiz_count
                    })
            
            questions_per_topic = []
            
            topic_counts = {}
            topic_names = {}
            all_topics = list(self.topics.find({}, {"topic_id": 1, "name": 1}))
            
            for topic in all_topics:
                topic_id = topic["topic_id"]
                topic_counts[topic_id] = 0
                topic_names[topic_id] = topic["name"]
            
            approved_questions_cursor = self.questions.find({"is_approved": True})
            for question in approved_questions_cursor:
                topic_id = question.get("topic_id")
                if topic_id in topic_counts:
                    topic_counts[topic_id] += 1
            
            for topic_id, count in topic_counts.items():
                questions_per_topic.append({
                    "topic_id": topic_id,
                    "topic_name": topic_names[topic_id],
                    "question_count": count
                })
            
            questions_per_topic.sort(key=lambda x: x["question_count"], reverse=True)
            
            invalid_topics = []
            topic_ids = set(topic_names.keys())
            invalid_count = 0
            
            for question in self.questions.find({"is_approved": True}):
                topic_id = question.get("topic_id")
                if not topic_id or topic_id not in topic_ids:
                    invalid_count += 1
                    invalid_topics.append(question.get("question_id", "unknown"))
            
            logger.info(f"Generated bot statistics: {users_count} users, {topics_count} topics, {total_questions} questions")
            
            return {
                "status": "success",
                "statistics": {
                    "users": {
                        "total": users_count,
                        "started": started_users_count,
                        "new_24h": today_users_count
                    },
                    "topics": {
                        "total": topics_count,
                        "active": active_topics_count,
                        "popular": popular_topics
                    },
                    "questions": {
                        "total": total_questions,
                        "approved": approved_questions,
                        "pending": pending_questions,
                        "top_submitters": top_submitters,
                        "top_creators": top_creators,
                        "per_topic": questions_per_topic,
                        "invalid_topics": invalid_topics,
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error generating bot statistics: {str(e)}")
            return {
                "status": "error",
                "message": f"Error generating statistics: {str(e)}"
            }
        
    
    
    
    
    