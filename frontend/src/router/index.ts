import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../pages/HomeView.vue'
import NewsView from '../pages/NewsView.vue'
import NoteView from '../pages/NoteView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', component: HomeView },
    { path: '/notes/:id', component: NoteView },
    { path: '/news/:id', component: NewsView },
  ],
})

export default router
