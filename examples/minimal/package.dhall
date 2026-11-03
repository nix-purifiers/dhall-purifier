let sum =
      https://raw.githubusercontent.com/dhall-lang/dhall-lang/v20.1.0/Prelude/Natural/sum
        sha256:33f7f4c3aff62e5ecf4848f964363133452d420dcde045784518fb59fa970037

in  { answer = sum [ 20, 22 ] }
