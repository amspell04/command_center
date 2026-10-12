import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../pages/HomeView.vue'
import MonthView from '../pages/MonthView.vue'
import NoteView from '../pages/NoteView.vue'
import TrainingView from '../pages/TrainingView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', component: HomeView },
    { path: '/calendar', component: MonthView },
    { path: '/notes/:id', component: NoteView },
    { path: '/training', component: TrainingView },
  ],
})

export default router
