# importing required libraries
import os
import random
import datetime
from dotenv import load_dotenv
import telebot
from telebot import types
from Predefined import greetings

import logging
import base64
import time
import requests
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from io import BytesIO
from PIL import Image
import openai




# Load environment variables
load_dotenv('.env')
# Configure logging
logging.basicConfig(level=logging.INFO)

# Get the Telegram Bot API Key
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
# Initialize the OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))








# ============ MOVIE RECOMMENDATION FUNCTIONS ============

class MovieRecommender:
    def __init__(self):
        self.movies_df = None
        self.tfidf_matrix = None
        self.tfidf_vectorizer = None
        self.load_movie_data()

    def load_movie_data(self):
        """Load and prepare movie data from TMDB"""
        try:
            # Check if we have cached data
            if os.path.exists('movie_data.csv'):
                logging.info("Loading cached movie data")
                self.movies_df = pd.read_csv('movie_data.csv')
                # Prepare TF-IDF vectors
                self.prepare_vectors()
                return

            # If no cached data, fetch from TMDB
            logging.info("Fetching movie data from TMDB")
            movies = []
            
            # Fetch popular movies (first 10 pages)
            for page in range(1, 11):
                url = f"https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}&language=en-US&page={page}"
                response = requests.get(url)
                if response.status_code == 200:
                    results = response.json()['results']
                    for movie in results:
                        # Only include movies with overviews
                        if movie['overview']:
                            movies.append({
                                'id': movie['id'],
                                'title': movie['title'],
                                'overview': movie['overview'],
                                'genres': self._get_movie_genres(movie['id']),
                                'poster_path': movie['poster_path'],
                                'vote_average': movie['vote_average']
                            })
                else:
                    logging.error(f"Error fetching movies: {response.status_code}")
            
            # Create DataFrame and save to cache
            self.movies_df = pd.DataFrame(movies)
            self.movies_df.to_csv('movie_data.csv', index=False)
            
            # Prepare TF-IDF vectors
            self.prepare_vectors()
            
        except Exception as e:
            logging.error(f"Error loading movie data: {str(e)}")
            # If error occurs, create an empty DataFrame to avoid None errors
            self.movies_df = pd.DataFrame(columns=['id', 'title', 'overview', 'genres', 'poster_path', 'vote_average'])
            self.tfidf_matrix = np.array([])
    
    def _get_movie_genres(self, movie_id):
        """Get genres for a specific movie"""
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
        response = requests.get(url)
        if response.status_code == 200:
            genres = response.json().get('genres', [])
            return ", ".join([genre['name'] for genre in genres])
        return ""
    
    def prepare_vectors(self):
        """Prepare TF-IDF vectors from movie overviews"""
        if self.movies_df is None or self.movies_df.empty:
            logging.warning("No movie data available for vectorization")
            return
        
        # Create TF-IDF vectorizer
        self.tfidf_vectorizer = TfidfVectorizer(stop_words='english')
        
        # Transform movie overviews to TF-IDF vectors
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(self.movies_df['overview'])
        logging.info(f"Created TF-IDF matrix with shape {self.tfidf_matrix.shape}")
    
    def get_recommendation_by_description(self, user_description, num_recommendations=1):
        """Get movie recommendations based on user description"""
        if self.tfidf_matrix is None or self.tfidf_vectorizer is None or self.movies_df is None or self.movies_df.empty:
            logging.error("Recommendation system not properly initialized")
            return None
        
        try:
            # Transform user description to TF-IDF vector
            user_vector = self.tfidf_vectorizer.transform([user_description])
            
            # Calculate similarity scores
            similarity_scores = cosine_similarity(user_vector, self.tfidf_matrix).flatten()
            
            # Get indices of top recommendations
            top_indices = similarity_scores.argsort()[::-1][:num_recommendations]
            
            # Get recommended movies
            recommendations = []
            for idx in top_indices:
                movie = self.movies_df.iloc[idx]
                
                # Get poster URL
                poster_url = None
                if movie['poster_path']:
                    poster_url = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                
                recommendations.append({
                    'title': movie['title'],
                    'genres': movie['genres'],
                    'overview': movie['overview'],
                    'rating': movie['vote_average'],
                    'poster_url': poster_url
                })
            
            return recommendations[0] if recommendations else None
        
        except Exception as e:
            logging.error(f"Error getting recommendation: {str(e)}")
            return None




# Initialize movie recommender
recommender = MovieRecommender()
