// SPDX-License-Identifier: MIT

export function buildCityTeleportGroups(cities, regions) {
  const regionList = Array.isArray(regions) ? regions : [];
  const cityList = Array.isArray(cities) ? cities : [];
  const groups = regionList
    .filter(region => region && typeof region.id === 'string')
    .map(region => ({
      id: region.id,
      name: String(region.name || region.id),
      cities: [],
    }));
  const groupsById = new Map(groups.map(group => [group.id, group]));
  const other = { id: 'other', name: 'Other', cities: [] };

  for (const city of cityList) {
    if (!city || typeof city.id !== 'string' || typeof city.name !== 'string') continue;
    const group = groupsById.get(city.region) || other;
    group.cities.push({ id: city.id, name: city.name });
  }

  for (const group of [...groups, other]) {
    group.cities.sort((a, b) => a.name.localeCompare(b.name));
  }

  if (other.cities.length > 0) groups.push(other);
  return groups.filter(group => group.cities.length > 0);
}

export function resolveTeleportCity(cities, cityId) {
  if (!Array.isArray(cities) || typeof cityId !== 'string' || cityId === '') return null;
  return cities.find(city => city?.id === cityId) || null;
}
