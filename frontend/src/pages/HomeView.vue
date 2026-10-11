<script setup lang="ts">
import { RouterLink } from 'vue-router'
import GoalsPanel from '@/components/GoalsPanel.vue'
import NewsBriefing from '@/components/NewsBriefing.vue'
import NotesPanel from '@/components/NotesPanel.vue'
import ProgressTicker from '@/components/ProgressTicker.vue'
import TasksPanel from '@/components/TasksPanel.vue'
import TodayPanel from '@/components/TodayPanel.vue'
import WeekTimeline from '@/components/WeekTimeline.vue'
</script>

<template>
  <ProgressTicker />
  <main class="home">
    <div class="home__week">
      <nav class="home__nav" aria-label="Sections">
        <RouterLink to="/calendar" class="nav-link">Calendar →</RouterLink>
        <RouterLink to="/training" class="nav-link">Training →</RouterLink>
      </nav>
      <WeekTimeline />
    </div>
    <TodayPanel class="home__col home__today" />
    <TasksPanel class="home__col home__tasks" />
    <aside class="home__col home__side">
      <GoalsPanel />
      <NotesPanel />
    </aside>
    <NewsBriefing class="home__news" />
  </main>
</template>

<style scoped>
.home {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) minmax(0, 1fr);
  grid-template-areas:
    'week week week'
    'today tasks side'
    'news news news';
  max-width: 1680px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-5);
}
.home__week {
  grid-area: week;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
}
.home__nav {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-1);
  margin-bottom: var(--space-1);
}
.home__col {
  padding: var(--space-3) var(--space-4);
  border-left: 1px solid var(--border-color);
}
.home__today {
  grid-area: today;
  padding-left: 0;
  border-left: none;
}
.home__tasks {
  grid-area: tasks;
}
.home__news {
  grid-area: news;
  margin-top: var(--space-3);
  padding: var(--space-3) 0 0;
  border-top: 1px solid var(--border-color);
}
.home__side {
  grid-area: side;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
@media (max-width: 1100px) {
  .home {
    grid-template-columns: 1fr 1fr;
    grid-template-areas: 'week week' 'today today' 'tasks side' 'news news';
  }
  .home__today {
    padding-right: 0;
    border-bottom: 1px solid var(--border-color);
  }
  .home__tasks {
    padding-left: 0;
    border-left: none;
  }
}
@media (max-width: 700px) {
  .home {
    grid-template-columns: 1fr;
    grid-template-areas: 'week' 'today' 'tasks' 'side' 'news';
    padding: var(--space-3);
  }
  .home__col {
    padding-left: 0;
    border-left: none;
  }
}
</style>
