<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent, AuthFormField } from '@nuxt/ui'
import { useAuth } from '~/composables/auth/useAuth'
import { useSetupStatus } from '~/composables/auth/useSetupStatus'
import { usePageSeo } from '~/composables/usePageSeo'

definePageMeta({
  layout: 'auth',
})

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const { registerInitialAdmin } = useAuth()
const { markConfigured } = useSetupStatus()
const submitting = ref(false)
const setupForm = useTemplateRef<{ state?: Record<string, unknown> }>('setupForm')

usePageSeo({
  title: () => t('pages.auth.setupTitle'),
  description: () => t('pages.auth.setupDescription'),
  robots: 'index, follow',
})

function buildFields(): AuthFormField[] {
  return [
    {
      name: 'email',
      type: 'email',
      size: 'lg',
      label: t('pages.auth.email'),
      placeholder: t('pages.auth.emailPlaceholder'),
      required: true,
      autocomplete: 'username',
      defaultValue: '',
    },
    {
      name: 'password',
      type: 'password',
      size: 'lg',
      label: t('pages.auth.password'),
      placeholder: t('pages.auth.passwordPlaceholder'),
      required: true,
      autocomplete: 'new-password',
      defaultValue: '',
    },
  ]
}

const fields = ref<AuthFormField[]>(buildFields())

watch(locale, () => {
  fields.value = buildFields()
})

// Mirrors the backend SetupRequest: email format + the shared 6-char minimum.
const schema = computed(() => z.object({
  email: z.email({ error: t('pages.auth.emailRequired') }),
  password: z.string().min(6, { error: t('pages.auth.passwordRequired') }),
}))

type Schema = {
  email: string
  password: string
}

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  if (submitting.value) return

  submitting.value = true
  try {
    const formState = setupForm.value?.state || {}
    const email = String(payload.data?.email ?? formState.email ?? '').trim()
    const password = String(payload.data?.password ?? formState.password ?? '')
    const result = await registerInitialAdmin({ email, password })
    const user = result.data?.user
    if (!user) throw new Error('Setup failed')

    auth.login(user)
    markConfigured()
    await router.replace('/')
  }
  catch {
    toast.add({
      title: t('pages.auth.setupFailed'),
      description: t('pages.auth.setupFailedDesc'),
      color: 'error',
    })
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center">
    <UAuthForm
      ref="setupForm"
      :schema="schema"
      :title="t('pages.auth.setupTitle')"
      icon="i-lucide-shield-check"
      :fields="fields"
      :loading="submitting"
      :submit="{
        label: t('pages.auth.setupBtn'),
        class: 'w-full h-10! text-xl font-normal',
        loading: submitting,
      }"
      @submit="onSubmit"
    >
      <template #leading>
        <div class="mx-auto flex size-24 items-center justify-center overflow-hidden">
          <img src="/logo.png" alt="HollyWing Motor" class="h-full w-full object-contain p-1">
        </div>
      </template>

      <template #description>
        <p class="text-sm text-muted">{{ t('pages.auth.setupDescription') }}</p>
      </template>

      <template #footer>
        <div class="text-center">
          <span class="text-sm font-normal text-muted">{{ $t('settings.aboutCopyright') }}</span>
        </div>
      </template>
    </UAuthForm>
  </div>
</template>
