import React, { useState } from 'react';
import { Star, Send, Loader } from 'lucide-react';

const FeedbackCard = ({ receiptId, onSubmit, isSubmitted, reward }) => {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [hoveredRating, setHoveredRating] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (rating === 0) {
      alert('Please select a rating');
      return;
    }

    if (!comment.trim()) {
      alert('Please enter a comment');
      return;
    }

    setIsSubmitting(true);
    try {
      const feedbackData = { rating, comment };
      await onSubmit(receiptId, feedbackData);
    } catch (error) {
      console.error('Error submitting feedback:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="mt-4">
        <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-green-400/15 via-green-300/10 to-green-500/20 backdrop-blur-sm border border-green-200/25 shadow-lg">
          <div className="relative p-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-r from-green-500 to-green-600 flex items-center justify-center">
                <Star className="w-5 h-5 text-white fill-white" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-green-800">Thank You!</h3>
                <p className="text-xs text-green-600">Your feedback has been submitted</p>
              </div>
            </div>
            
            {reward && (
              <div className="p-3 rounded-lg bg-gradient-to-r from-yellow-400/20 to-orange-400/20 border border-yellow-500/30">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-yellow-700">🎁 You earned {reward} LEMO!</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4">
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-purple-400/15 via-purple-300/10 to-purple-500/20 backdrop-blur-sm border border-purple-200/25 shadow-lg">
        <div className="relative p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-6 h-6 rounded-full bg-gradient-to-r from-purple-500 to-purple-600 flex items-center justify-center">
              <Star className="w-3 h-3 text-white fill-white" />
            </div>
            <h3 className="text-sm font-bold text-purple-800">Share Your Feedback</h3>
          </div>
          
          <div className="mb-3">
            <div className="text-xs text-gray-600 mb-2">Rating</div>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHoveredRating(star)}
                  onMouseLeave={() => setHoveredRating(0)}
                  className="focus:outline-none transition-all"
                >
                  <Star
                    className={`w-6 h-6 transition-all ${
                      star <= (hoveredRating || rating)
                        ? 'text-yellow-400 fill-yellow-400'
                        : 'text-gray-300'
                    }`}
                  />
                </button>
              ))}
            </div>
            {rating > 0 && (
              <div className="text-xs text-gray-600 mt-1">
                {rating === 1 && 'Poor'}
                {rating === 2 && 'Fair'}
                {rating === 3 && 'Good'}
                {rating === 4 && 'Very Good'}
                {rating === 5 && 'Excellent'}
              </div>
            )}
          </div>
          
          <div className="mb-3">
            <div className="text-xs text-gray-600 mb-1">Comment</div>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Tell us about your experience..."
              className="w-full bg-white/40 backdrop-blur-sm border border-purple-200/50 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-500/50"
              rows={3}
            />
          </div>
          
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || rating === 0 || !comment.trim()}
            className="w-full bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 text-white font-bold py-2.5 px-4 rounded-lg transition-all flex items-center justify-center gap-2 shadow-md hover:shadow-lg transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          >
            {isSubmitting ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                <span className="text-sm">Submitting...</span>
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                <span className="text-sm">Submit Feedback</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default FeedbackCard;

