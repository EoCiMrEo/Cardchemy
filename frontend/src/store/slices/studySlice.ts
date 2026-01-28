import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface StudyState {
  currentSessionId: string | null;
  cards: any[];
  currentIndex: number;
  results: Record<string, boolean>; // cardId -> isCorrect
  sessionComplete: boolean;
  timeLimit: number | null; // Seconds per card
}

const initialState: StudyState = {
  currentSessionId: null,
  cards: [],
  currentIndex: 0,
  results: {},
  sessionComplete: false,
  timeLimit: null,
};

export const studySlice = createSlice({
  name: 'study',
  initialState,
  reducers: {
    startSession: (state, action: PayloadAction<{ sessionId: string; cards: any[]; timeLimit?: number | null }>) => {
      state.currentSessionId = action.payload.sessionId;
      state.cards = action.payload.cards;
      state.timeLimit = action.payload.timeLimit || null;
      state.currentIndex = 0;
      state.results = {};
      state.sessionComplete = false;
    },
    answerCard: (state, action: PayloadAction<{ cardId: string; isCorrect: boolean }>) => {
      state.results[action.payload.cardId] = action.payload.isCorrect;
    },
    nextCard: (state) => {
      if (state.currentIndex < state.cards.length - 1) {
        state.currentIndex += 1;
      } else {
        state.sessionComplete = true;
      }
    },
    resetSession: (state) => {
        state.currentIndex = 0;
        state.results = {};
        state.sessionComplete = false;
    },
    clearSession: (state) => {
        state.currentSessionId = null;
        state.cards = [];
    }
  },
});

export const { startSession, answerCard, nextCard, resetSession, clearSession } = studySlice.actions;
export default studySlice.reducer;
