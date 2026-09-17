/** Preset select options that also accept user-typed custom values (UInputMenu create-item). */
export function useCreatableOptionList(defaults: readonly string[]) {
  const items = ref<string[]>([...defaults])

  function reset() {
    items.value = [...defaults]
  }

  function onCreate(item: string) {
    const trimmed = item.trim()
    if (!trimmed) return
    if (!items.value.includes(trimmed)) {
      items.value.push(trimmed)
    }
    return trimmed
  }

  return { items, reset, onCreate }
}
