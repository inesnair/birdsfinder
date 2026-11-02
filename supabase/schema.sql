-- =====================================================================
-- BirdsFinder : base de données Supabase
-- À exécuter une fois : Supabase > SQL Editor > New query > coller > Run.
-- Ré-exécutable sans risque (if not exists / or replace / drop policy if exists).
--
-- Principe de sécurité : la clé "anon" du front est publique. Ce sont les règles
-- Row Level Security (RLS) ci-dessous qui garantissent que chaque compte ne lit
-- et ne modifie QUE ses propres lignes. Les rôles (amateur / pro / admin) ne
-- peuvent pas être modifiés depuis l'application.
-- =====================================================================

-- ---------- 1. Profils ----------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) <= 120),
  role text not null default 'amateur' check (role in ('amateur', 'pro', 'admin')),
  pro_requested boolean not null default false,
  organisation text check (char_length(organisation) <= 120),
  terms_accepted_at timestamptz,
  created_at timestamptz not null default now()
);
alter table public.profiles enable row level security;

drop policy if exists "profil : lire le sien" on public.profiles;
create policy "profil : lire le sien" on public.profiles
  for select to authenticated using (id = (select auth.uid()));
drop policy if exists "profil : modifier le sien" on public.profiles;
create policy "profil : modifier le sien" on public.profiles
  for update to authenticated using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- Seules ces colonnes sont modifiables par l'utilisateur (pas "role")
revoke insert, update, delete on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;
grant update (display_name, pro_requested, organisation, terms_accepted_at) on public.profiles to authenticated;

-- Profil créé automatiquement à la première connexion Google
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, left(coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'), 120))
  on conflict (id) do nothing;
  return new;
end;
$$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- Aides utilisées dans les règles (security definer : évite les boucles RLS)
create or replace function public.is_pro() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role in ('pro', 'admin'));
$$;
create or replace function public.has_accepted_terms() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = auth.uid() and terms_accepted_at is not null);
$$;

-- ---------- 2. Ornithotèque ----------
create table if not exists public.observations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  region text not null check (region in ('antilles', 'europe')),
  species_id text not null check (char_length(species_id) <= 120),
  species_fr text check (char_length(species_fr) <= 120),
  species_sci text check (char_length(species_sci) <= 120),
  confidence real check (confidence between 0 and 1),
  model_version text check (char_length(model_version) <= 80),
  observed_at timestamptz not null default now(),
  latitude double precision check (latitude between -90 and 90),
  longitude double precision check (longitude between -180 and 180),
  location_source text not null default 'none' check (location_source in ('device', 'exif', 'none')),
  note text check (char_length(note) <= 500),
  created_at timestamptz not null default now(),
  -- lieu : les deux coordonnées ou aucune, et une source cohérente
  constraint lieu_complet check ((latitude is null) = (longitude is null)),
  constraint lieu_source check ((latitude is null) = (location_source = 'none'))
);
create index if not exists observations_user_date on public.observations (user_id, observed_at desc);
alter table public.observations enable row level security;

drop policy if exists "observations : lire les siennes" on public.observations;
create policy "observations : lire les siennes" on public.observations
  for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "observations : ajouter" on public.observations;
create policy "observations : ajouter" on public.observations
  for insert to authenticated with check (user_id = (select auth.uid()) and public.has_accepted_terms());
drop policy if exists "observations : modifier les siennes" on public.observations;
create policy "observations : modifier les siennes" on public.observations
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists "observations : supprimer les siennes" on public.observations;
create policy "observations : supprimer les siennes" on public.observations
  for delete to authenticated using (user_id = (select auth.uid()));

-- ---------- 3. Corrections (comptes professionnels) ----------
create table if not exists public.corrections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  region text not null check (region in ('antilles', 'europe')),
  predicted_species_id text not null check (char_length(predicted_species_id) <= 120),
  predicted_confidence real check (predicted_confidence between 0 and 1),
  proposed_species_id text check (char_length(proposed_species_id) <= 120),
  proposed_species_other text check (char_length(proposed_species_other) <= 120),
  comment text check (char_length(comment) <= 500),
  model_version text check (char_length(model_version) <= 80),
  photo_path text not null,
  consent_training boolean not null check (consent_training),
  status text not null default 'pending' check (status in ('pending', 'accepted', 'rejected')),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint une_espece_proposee check ((proposed_species_id is null) <> (proposed_species_other is null)),
  constraint photo_dans_son_dossier check (photo_path like (user_id::text || '/%'))
);
alter table public.corrections enable row level security;

drop policy if exists "corrections : lire les siennes" on public.corrections;
create policy "corrections : lire les siennes" on public.corrections
  for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "corrections : envoyer (pros)" on public.corrections;
create policy "corrections : envoyer (pros)" on public.corrections
  for insert to authenticated
  with check (user_id = (select auth.uid()) and public.is_pro() and status = 'pending' and reviewed_at is null);
drop policy if exists "corrections : retirer les siennes" on public.corrections;
create policy "corrections : retirer les siennes" on public.corrections
  for delete to authenticated using (user_id = (select auth.uid()));
-- Pas de modification par l'utilisateur : la validation se fait côté administration (clé service, Colab)
revoke update on public.corrections from anon, authenticated;

-- ---------- 4. Photos de correction (stockage privé) ----------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('corrections', 'corrections', false, 2097152, array['image/jpeg'])
on conflict (id) do update set public = false, file_size_limit = 2097152, allowed_mime_types = array['image/jpeg'];

drop policy if exists "photos : envoi par les pros dans leur dossier" on storage.objects;
create policy "photos : envoi par les pros dans leur dossier" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'corrections' and (storage.foldername(name))[1] = (select auth.uid())::text and public.is_pro());
drop policy if exists "photos : lire les siennes" on storage.objects;
create policy "photos : lire les siennes" on storage.objects
  for select to authenticated
  using (bucket_id = 'corrections' and (storage.foldername(name))[1] = (select auth.uid())::text);
drop policy if exists "photos : supprimer les siennes" on storage.objects;
create policy "photos : supprimer les siennes" on storage.objects
  for delete to authenticated
  using (bucket_id = 'corrections' and (storage.foldername(name))[1] = (select auth.uid())::text);

-- ---------- 5. Droit à l'effacement : suppression de son compte ----------
-- Le front supprime d'abord les photos (API Storage), puis appelle cette fonction.
-- Profil, observations et corrections suivent par "on delete cascade".
create or replace function public.delete_my_account() returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then
    raise exception 'Non connecté';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;
revoke execute on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
