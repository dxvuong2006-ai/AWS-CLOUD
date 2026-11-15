BEGIN;

DELETE FROM public.users
WHERE id = 20
  AND email = 'bchuy331@gmail.com'
  AND role = 'ADMIN'
  AND EXISTS (
      SELECT 1 FROM public.users
      WHERE role = 'ADMIN'
        AND status = 'ACTIVE'
        AND id <> 20
  )
RETURNING id, email, role;